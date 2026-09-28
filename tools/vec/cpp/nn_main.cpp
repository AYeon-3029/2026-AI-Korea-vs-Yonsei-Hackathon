// 신경망 정책 봇(C++20, 제출용). 가중치는 weights.hpp 에 float16 정수 배열로 들어 있다(tools/vec/export_cpp.py 가 생성).
// 관측 인코딩은 Model/sparring/rlbot/enc.py, 행동은 rlbot/main.py 의 확률 비례 분할(RL_PROP=1)과 같다.
// 외부 파일을 읽지 않는다. stderr 에는 턴마다 추론 시간(ms)만 적는다(게임당 1 MiB 이내).
#pragma GCC optimize("O3")
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "weights.hpp"  // NN_CH, NN_BLOCKS, NN_W16[], NN_* 오프셋

namespace {

constexpr int H = 15, W = 15, HW = 225, PHW = 232;  // PHW: 8의 배수로 패딩(벡터화)
constexpr int C = 30;
const char* TYPES[8] = {"PLAZA", "HALL", "ENG", "HOSPITAL", "LIBRARY", "DEPOT", "STATION", "WATCH"};
const int F_CHOICES[3] = {0, 1, 2};
const double W_FRACS[4] = {0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0};
const char* DIRS[4] = {"U", "D", "L", "R"};
const int DX[4] = {0, 0, -1, 1}, DY[4] = {-1, 1, 0, 0};

float h2f(uint16_t h) {
    uint32_t s = (h >> 15) & 1, e = (h >> 10) & 31, m = h & 1023, f;
    if (e == 0) {
        if (m == 0) f = s << 31;
        else {  // 비정규 수
            e = 127 - 15 + 1;
            while (!(m & 1024)) { m <<= 1; e--; }
            m &= 1023;
            f = (s << 31) | (e << 23) | (m << 13);
        }
    } else if (e == 31) f = (s << 31) | (255u << 23) | (m << 13);
    else f = (s << 31) | ((e - 15 + 127) << 23) | (m << 13);
    float out;
    std::memcpy(&out, &f, 4);
    return out;
}

std::vector<float> WT;  // 전체 가중치(float32)

// ------------------------------------------------------------------ 합성곱(im2col + 8 출력 동시 누적)
// 서버 GCC 에서는 AVX2 판과 기본 판을 함께 만들어 실행 시 CPU 에 맞게 고른다(AVX2 없는 CPU 에서도 안전).
// clang(로컬 검증용 zig c++)은 이 기능의 런타임 기호가 없어 기본 판만 쓴다 → 로컬 시간 측정은 보수적이다.
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((target_clones("avx2", "default")))
#endif
void gemm(const float* w, const float* b, const float* col, int cout, int K, float* out) {
    // out[co][p] = b[co] + Σ_j w[co][j] · col[j][p]   (p < PHW)
    int co = 0;
    for (; co + 8 <= cout; co += 8) {
        float* o[8];
        for (int r = 0; r < 8; r++) {
            o[r] = out + (co + r) * PHW;
            for (int p = 0; p < PHW; p++) o[r][p] = b[co + r];
        }
        for (int j = 0; j < K; j++) {
            const float* c = col + j * PHW;
            float wv[8];
            for (int r = 0; r < 8; r++) wv[r] = w[(co + r) * K + j];
            for (int p = 0; p < PHW; p++) {
                float cv = c[p];
                o[0][p] += wv[0] * cv; o[1][p] += wv[1] * cv; o[2][p] += wv[2] * cv; o[3][p] += wv[3] * cv;
                o[4][p] += wv[4] * cv; o[5][p] += wv[5] * cv; o[6][p] += wv[6] * cv; o[7][p] += wv[7] * cv;
            }
        }
    }
    for (; co < cout; co++) {
        float* o = out + co * PHW;
        for (int p = 0; p < PHW; p++) o[p] = b[co];
        for (int j = 0; j < K; j++) {
            const float* c = col + j * PHW;
            float wv = w[co * K + j];
            for (int p = 0; p < PHW; p++) o[p] += wv * c[p];
        }
    }
}

std::vector<float> COL;

void conv3(const float* in, int cin, int cout, size_t woff, size_t boff, float* out) {
    COL.assign((size_t)cin * 9 * PHW, 0.f);
    for (int ci = 0; ci < cin; ci++)
        for (int ky = 0; ky < 3; ky++)
            for (int kx = 0; kx < 3; kx++) {
                float* c = COL.data() + ((size_t)(ci * 9 + ky * 3 + kx)) * PHW;
                const float* src = in + ci * PHW;
                for (int y = 0; y < H; y++) {
                    int sy = y + ky - 1;
                    if (sy < 0 || sy >= H) continue;
                    for (int x = 0; x < W; x++) {
                        int sx = x + kx - 1;
                        if (sx < 0 || sx >= W) continue;
                        c[y * W + x] = src[sy * W + sx];
                    }
                }
            }
    gemm(WT.data() + woff, WT.data() + boff, COL.data(), cout, cin * 9, out);
}

void relu(float* a, int n) { for (int i = 0; i < n; i++) a[i] = a[i] > 0 ? a[i] : 0; }

// ------------------------------------------------------------------ 게임 입력
struct Bld { int id, x, y; std::string type; };
struct Init {
    int w = 15, h = 15; std::string team, opp; std::vector<std::string> terrain;
    std::vector<Bld> blds; int bx = 0, by = 0, ex = 0, ey = 0; bool flip = false;
    void fr(int x, int y, int& fx, int& fy) const {
        if (flip) { fx = w - 1 - x; fy = h - 1 - y; } else { fx = x; fy = y; }
    }
};

Init parse_init(const std::vector<std::string>& lines) {
    Init ini;
    for (size_t i = 0; i < lines.size(); i++) {
        std::istringstream ss(lines[i]);
        std::string t; ss >> t;
        if (t == "INIT") ss >> ini.w >> ini.h;
        else if (t == "TEAM") { ss >> ini.team; ini.opp = ini.team == "Y" ? "K" : "Y"; }
        else if (t == "MAP") { std::string r; ss >> r; ini.terrain.push_back(r); }
        else if (t == "BUILDINGS") {
            int n; ss >> n;
            for (int k = 0; k < n; k++) {
                std::istringstream bs(lines[++i]);
                Bld b; bs >> b.id >> b.x >> b.y >> b.type; ini.blds.push_back(b);
            }
        } else if (t == "BASE") {
            std::string tm; int x, y; ss >> tm >> x >> y;
            if (tm == ini.team) { ini.bx = x; ini.by = y; } else { ini.ex = x; ini.ey = y; }
        }
    }
    ini.flip = ini.bx * 2 > ini.w - 1;
    return ini;
}

struct Turn {
    int turn = 0, my_res = 0, opp_res = 0;
    struct U { std::string team, kind; int x, y, c; };
    struct B { int id, x, y; std::string type, owner; int stage, score; };
    std::vector<U> units; std::vector<B> blds;
};

Turn parse_turn(const std::vector<std::string>& lines) {
    Turn v;
    for (size_t i = 0; i < lines.size(); i++) {
        std::istringstream ss(lines[i]);
        std::string t; ss >> t;
        if (t == "TURN") ss >> v.turn;
        else if (t == "RESOURCE") ss >> v.my_res >> v.opp_res;
        else if (t == "UNITS") {
            int n; ss >> n;
            for (int k = 0; k < n; k++) {
                std::istringstream us(lines[++i]);
                Turn::U u; us >> u.team >> u.kind >> u.x >> u.y >> u.c; v.units.push_back(u);
            }
        } else if (t == "BUILDINGS") {
            int n; ss >> n;
            for (int k = 0; k < n; k++) {
                std::istringstream bs(lines[++i]);
                Turn::B b; bs >> b.id >> b.x >> b.y >> b.type >> b.owner >> b.stage >> b.score; v.blds.push_back(b);
            }
        }
    }
    return v;
}

// ------------------------------------------------------------------ 한 턴
std::vector<std::string> decide(const Init& ini, const Turn& v) {
    std::vector<float> obs((size_t)C * PHW, 0.f);
    auto O = [&](int ch, int fx, int fy) -> float& { return obs[(size_t)ch * PHW + fy * W + fx]; };
    int cnt[2][HW] = {};
    bool valid[4][HW] = {};
    int fx, fy;
    for (int y = 0; y < ini.h; y++)
        for (int x = 0; x < ini.w; x++) { ini.fr(x, y, fx, fy); O(0, fx, fy) = ini.terrain[y][x] != '#'; }
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            for (int d = 0; d < 4; d++) {
                int nx = x + DX[d], ny = y + DY[d];
                valid[d][y * W + x] = nx >= 0 && nx < W && ny >= 0 && ny < H && O(0, nx, ny) > 0;
            }
    ini.fr(ini.bx, ini.by, fx, fy); O(1, fx, fy) = 1;
    ini.fr(ini.ex, ini.ey, fx, fy); O(2, fx, fy) = 1;
    for (auto& b : ini.blds) {
        ini.fr(b.x, b.y, fx, fy);
        for (int k = 0; k < 8; k++) if (b.type == TYPES[k]) O(3 + k, fx, fy) = 1;
    }
    int eng_me = 0, eng_op = 0;
    for (auto& b : v.blds) {
        ini.fr(b.x, b.y, fx, fy);
        if (b.owner == ini.team) O(11, fx, fy) = 1;
        else if (b.owner == "N") { O(13, fx, fy) = 1; O(14, fx, fy) = b.stage == 1; }
        else O(12, fx, fy) = 1;
        if (b.score >= 0) O(15, fx, fy) = b.score / 4.0f; else O(16, fx, fy) = 1;
        if (b.type == "ENG") { if (b.owner == ini.team) eng_me++; else if (b.owner == ini.opp) eng_op++; }
    }
    for (auto& u : v.units) {
        ini.fr(u.x, u.y, fx, fy);
        bool mine = u.team == ini.team;
        if (u.kind == "F") { O(mine ? 17 : 19, fx, fy) += u.c / 4.0f; if (mine) cnt[0][fy * W + fx] += u.c; }
        else if (u.kind == "W") { O(mine ? 18 : 20, fx, fy) += u.c / 10.0f; if (mine) cnt[1][fy * W + fx] += u.c; }
        else O(mine ? 21 : 22, fx, fy) += u.c / 2.0f;
    }
    for (int p = 0; p < HW; p++) {
        obs[23 * PHW + p] = v.turn / 160.0f;
        obs[24 * PHW + p] = v.my_res / 40.0f;
        obs[25 * PHW + p] = v.opp_res / 40.0f;
        obs[26 * PHW + p] = eng_me / 2.0f;
        obs[27 * PHW + p] = eng_op / 2.0f;
    }
    for (auto& b : v.blds) {
        if (b.score < 0) continue;
        int xs[2] = {b.x, ini.w - 1 - b.x}, ys[2] = {b.y, ini.h - 1 - b.y};
        for (int k = 0; k < 2; k++) { ini.fr(xs[k], ys[k], fx, fy); O(28, fx, fy) = b.score / 4.0f; O(29, fx, fy) = 1; }
    }
    int wcost = std::max(2, 3 - eng_me);

    // 정책망
    const int ch = NN_CH;
    std::vector<float> x((size_t)ch * PHW), t1((size_t)ch * PHW), t2((size_t)ch * PHW);
    conv3(obs.data(), C, ch, NN_STEM_W, NN_STEM_B, x.data());
    relu(x.data(), ch * PHW);
    for (int bl = 0; bl < NN_BLOCKS; bl++) {
        conv3(x.data(), ch, ch, NN_BLK_W1[bl], NN_BLK_B1[bl], t1.data());
        relu(t1.data(), ch * PHW);
        conv3(t1.data(), ch, ch, NN_BLK_W2[bl], NN_BLK_B2[bl], t2.data());
        for (size_t i = 0; i < x.size(); i++) { float s = x[i] + t2[i]; x[i] = s > 0 ? s : 0; }
    }
    // 이동 로짓(1×1)
    std::vector<float> mv(10 * PHW);
    gemm(WT.data() + NN_MOVE_W, WT.data() + NN_MOVE_B, x.data(), 10, ch, mv.data());
    // 전역: 평균·최대 → 256 → F·W 생산
    std::vector<float> g(2 * ch), hdn(256);
    for (int c2 = 0; c2 < ch; c2++) {
        double s = 0; float m = -1e30f;
        for (int p = 0; p < HW; p++) { float a = x[(size_t)c2 * PHW + p]; s += a; m = std::max(m, a); }
        g[c2] = (float)(s / HW); g[ch + c2] = m;
    }
    for (int o = 0; o < 256; o++) {
        float s = WT[NN_GLOB_B + o];
        for (int i = 0; i < 2 * ch; i++) s += WT[NN_GLOB_W + (size_t)o * 2 * ch + i] * g[i];
        hdn[o] = s > 0 ? s : 0;
    }
    auto head = [&](size_t wo, size_t bo, int n) {
        int best = 0; float bv = -1e30f;
        for (int o = 0; o < n; o++) {
            float s = WT[bo + o];
            for (int i = 0; i < 256; i++) s += WT[wo + (size_t)o * 256 + i] * hdn[i];
            if (s > bv) { bv = s; best = o; }
        }
        return best;
    };
    int fi = head(NN_F_W, NN_F_B, 3), wi = head(NN_WF_W, NN_WF_B, 4);

    std::vector<std::string> out;
    int nF = std::min(F_CHOICES[fi], v.my_res / 5);
    int left = v.my_res - nF * 5;
    int nW = (int)std::floor(left * W_FRACS[wi]) / wcost;
    if (nF) out.push_back("SPAWN F " + std::to_string(nF));
    if (nW) out.push_back("SPAWN W " + std::to_string(nW));
    // 확률 비례 결정적 분할
    for (int k = 0; k < 2; k++)
        for (int p = 0; p < HW; p++) {
            int n = cnt[k][p];
            if (!n) continue;
            double lg[5], mx = -1e300;
            for (int d = 0; d < 5; d++) {
                bool ok = d == 0 || valid[d - 1][p];
                lg[d] = ok ? mv[(size_t)(k * 5 + d) * PHW + p] : -1e9;
                mx = std::max(mx, lg[d]);
            }
            double q[5], s = 0;
            for (int d = 0; d < 5; d++) { q[d] = std::exp(lg[d] - mx); s += q[d]; }
            int base[5], tot = 0;
            double frac[5];
            for (int d = 0; d < 5; d++) {
                q[d] /= s;
                base[d] = (int)std::floor(n * q[d]);
                frac[d] = n * q[d] - base[d];
                tot += base[d];
            }
            int idx[5] = {0, 1, 2, 3, 4};
            std::stable_sort(idx, idx + 5, [&](int a, int b) { return frac[a] > frac[b]; });
            for (int r = 0; r < n - tot; r++) base[idx[r]]++;
            int pfx = p % W, pfy = p / W, rx, ry;
            ini.fr(pfx, pfy, rx, ry);
            for (int d = 1; d < 5; d++) {
                if (!base[d]) continue;
                int dd = d - 1;
                if (ini.flip) dd = dd ^ 1;  // U↔D, L↔R
                out.push_back("MOVE " + std::to_string(rx) + " " + std::to_string(ry) + " " + (k ? "W" : "F") + " " +
                              std::to_string(base[d]) + " " + DIRS[dd]);
            }
        }
    return out;
}

}  // namespace

int main() {
    std::ios::sync_with_stdio(false);
    WT.resize(sizeof(NN_W16) / sizeof(NN_W16[0]));
    for (size_t i = 0; i < WT.size(); i++) WT[i] = h2f(NN_W16[i]);
    Init ini;
    bool have_init = false;
    std::vector<std::string> blk;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line != "END") { blk.push_back(line); continue; }
        if (!have_init) { ini = parse_init(blk); have_init = true; blk.clear(); continue; }
        auto t0 = std::chrono::steady_clock::now();
        std::vector<std::string> cmds;
        try { cmds = decide(ini, parse_turn(blk)); } catch (...) { cmds.clear(); }
        for (auto& c : cmds) std::cout << c << '\n';
        std::cout << "END\n" << std::flush;
        auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        std::fprintf(stderr, "%.1f\n", ms);
        blk.clear();
    }
}
