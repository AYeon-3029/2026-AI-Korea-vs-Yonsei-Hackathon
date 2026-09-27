// 참가자용 파싱·명령 출력 도우미. 표준 라이브러리만 사용한다.
#pragma once
#include "generated.hpp"
#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace p {
using namespace std;
struct Building { int id,x,y; string type,owner; int stage=0,score=-1; };
struct Unit { string team,kind; int x,y,count; };
struct Init {
    int width=0,height=0;string team,opp;vector<string>terrain;vector<Building>buildings;array<pair<int,int>,2>bases;
    bool passable(int x,int y)const{return x>=0&&y>=0&&x<width&&y<height&&terrain[y][x]!='#';}
    pair<int,int>base()const{return bases[team=="Y"?0:1];}
};
struct View {
    int turn=0,my_resource=0,opp_resource=0;vector<Unit>units;vector<Building>buildings;
    vector<Unit>my_units(const Init&i,const string&kind)const{
        vector<Unit>out;for(auto&u:units)if(u.team==i.team&&u.kind==kind)out.push_back(u);return out;
    }
    const Building*building_at(int x,int y)const{for(auto&b:buildings)if(b.x==x&&b.y==y)return &b;return nullptr;}
};
inline pair<int,int> delta(const string&d){
    if(d=="U")return {0,-1};if(d=="D")return {0,1};if(d=="L")return {-1,0};if(d=="R")return {1,0};
    throw runtime_error("알 수 없는 방향");
}
inline bool read_block(istream&in,vector<string>&lines){
    lines.clear();string line;while(getline(in,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();if(line==contract::END)return true;lines.push_back(line);}return false;
}
inline istringstream row(const vector<string>&lines,size_t index){if(index>=lines.size())throw runtime_error("입력 행이 부족합니다");return istringstream(lines[index]);}
inline void require(bool valid){if(!valid)throw runtime_error("입력 프로토콜 형식이 다릅니다");}
inline Init parse_init(const vector<string>&lines){
    Init i;string tag;auto head=row(lines,0);head>>tag>>i.width>>i.height;require(bool(head)&&tag==contract::INIT);
    auto team=row(lines,1);team>>tag>>i.team;require(bool(team)&&tag==contract::TEAM);i.opp=i.team=="Y"?"K":"Y";
    size_t index=2;for(int y=0;y<i.height;y++){string cells;auto r=row(lines,index++);r>>tag>>cells;require(bool(r)&&tag==contract::MAP&&int(cells.size())==i.width);i.terrain.push_back(cells);}
    int count;auto b=row(lines,index++);b>>tag>>count;require(bool(b)&&tag==contract::BUILDINGS);
    for(int n=0;n<count;n++){Building v;auto r=row(lines,index++);r>>v.id>>v.x>>v.y>>v.type;require(bool(r));i.buildings.push_back(v);}
    for(int n=0;n<2;n++){string t;int x,y;auto r=row(lines,index++);r>>tag>>t>>x>>y;require(bool(r)&&tag==contract::BASE);i.bases[t=="Y"?0:1]={x,y};}
    require(index==lines.size());return i;
}
inline View parse_turn(const vector<string>&lines,const Init&){
    View v;string tag;auto h=row(lines,0);h>>tag>>v.turn;require(bool(h)&&tag==contract::TURN);
    auto r=row(lines,1);r>>tag>>v.my_resource>>v.opp_resource;require(bool(r)&&tag==contract::RESOURCE);
    size_t index=2;int count;auto u=row(lines,index++);u>>tag>>count;require(bool(u)&&tag==contract::UNITS);
    for(int n=0;n<count;n++){Unit a;auto q=row(lines,index++);q>>a.team>>a.kind>>a.x>>a.y>>a.count;require(bool(q));v.units.push_back(a);}
    auto b=row(lines,index++);b>>tag>>count;require(bool(b)&&tag==contract::BUILDINGS);
    for(int n=0;n<count;n++){Building a;auto q=row(lines,index++);q>>a.id>>a.x>>a.y>>a.type>>a.owner>>a.stage>>a.score;require(bool(q));v.buildings.push_back(a);}
    require(index==lines.size());return v;
}
inline string spawn(const string&kind,int count){return contract::CMD_SPAWN+" "+kind+" "+to_string(count);}
inline string spawn(const string&kind,int count,int x,int y){return spawn(kind,count)+" "+to_string(x)+" "+to_string(y);}
inline string move(int x,int y,const string&kind,int count,const string&direction){return contract::CMD_MOVE+" "+to_string(x)+" "+to_string(y)+" "+kind+" "+to_string(count)+" "+direction;}
inline string move2(int x,int y,int count,const string&a,const string&b){return contract::CMD_MOVE2+" "+to_string(x)+" "+to_string(y)+" S "+to_string(count)+" "+a+" "+b;}
inline string tele(int x,int y,const string&kind,int count,int tx,int ty){return contract::CMD_TELE+" "+to_string(x)+" "+to_string(y)+" "+kind+" "+to_string(count)+" "+to_string(tx)+" "+to_string(ty);}
inline string priority(const vector<pair<int,int>>&coords){string out=contract::CMD_PRIORITY;for(auto [x,y]:coords)out+=" "+to_string(x)+" "+to_string(y);return out;}
inline void emit(const vector<string>&commands,ostream&out=cout){for(auto&c:commands)out<<c<<'\n';out<<contract::END<<'\n';out.flush();}
inline int run(const function<vector<string>(const View&,const Init&)>&decide){
    try{vector<string>lines;if(!read_block(cin,lines))return 0;Init i=parse_init(lines);while(read_block(cin,lines))emit(decide(parse_turn(lines,i),i));return 0;}
    catch(const exception&e){cerr<<"봇 입력 처리 오류: "<<e.what()<<'\n';return 1;}
}
}
