// Reviewed weekly series through Izzi's native line-graph and marker APIs.
#include "izzi-svg.h"
#include "izzi-svg-graphs-line.h"
#include <rapidjson/document.h>
#include <fstream>
#include <iomanip>

using std::string;
string number(double x) { std::ostringstream s; s<<std::fixed<<std::setprecision(5)<<x;return s.str(); }
void text(svg::svg_element& out,double x,double y,const string& s,int size=18,const string& anchor="start") {
  out.add_raw("<text x=\""+number(x)+"\" y=\""+number(y)+"\" font-family=\"DejaVu Sans,sans-serif\" font-size=\""+std::to_string(size)+"\" text-anchor=\""+anchor+"\" fill=\"#26313a\">"+svg::escape_xml_attribute(s)+"</text>");
}
svg::color_qi parse_color(const string& value) {
  return svg::color_qi(std::stoi(value.substr(1,2),nullptr,16),std::stoi(value.substr(3,2),nullptr,16),std::stoi(value.substr(5,2),nullptr,16));
}
string label(double v,bool percent) {
  const double scale=percent?1:(v>=1000000?1000000:(v>=1000?1000:1));
  std::ostringstream s;s<<std::setprecision(3)<<v/scale;
  return s.str()+(percent?"%":(scale==1000000?"m":scale==1000?"k":""));
}
double ceiling(double value) {
  if(value<=0)return 1;
  const double base=std::pow(10.,std::floor(std::log10(value)));
  return std::ceil(value/base*2)/2*base;
}
int main(int argc,char** argv) {
  if(argc!=3)return 2;
  std::ifstream input(argv[1]);string raw((std::istreambuf_iterator<char>(input)),{});
  rapidjson::Document doc;doc.Parse(raw.c_str());if(doc.HasParseError())throw std::runtime_error("invalid chart JSON");
  using namespace svg;
  const int columns=doc["columns"].GetInt(),rows=(doc["panels"].Size()+columns-1)/columns;
  const double width=1200,cell=width/columns,plot_width=cell-125,plot_height=columns==1?255:270;
  const auto& legend=doc["panels"][0]["series"];
  const int legend_cols=legend.Size()>4?3:2,legend_rows=(legend.Size()+legend_cols-1)/legend_cols;
  const double header=100+legend_rows*28,panel_height=plot_height+130,height=header+rows*panel_height+25;
  svg_element out(argv[2],area<>{width,height});
  out.add_raw("<rect width=\"100%\" height=\"100%\" fill=\"white\"/>");
  text(out,25,32,doc["title"].GetString(),25);text(out,25,62,doc["subtitle"].GetString(),17);
  const marker_shape forms[]={marker_shape::circle,marker_shape::square,marker_shape::triangle,marker_shape::hexagon,marker_shape::x,marker_shape::octahedron,marker_shape::sunburst};
  for(rapidjson::SizeType j=0;j<legend.Size();++j) {
    const auto& s=legend[j];const double x=30+(j%legend_cols)*(width/legend_cols),y=96+(j/legend_cols)*28;
    style sty={parse_color(s["color"].GetString()),1,parse_color(s["color"].GetString()),1,2};
    stroke_style stroke={"",forms[j%7],0,s["dash"].GetString(),"","round",""};
    out.add_element(make_polyline({{x,y-5},{x+42,y-5}},sty,stroke));
    out.add_raw(make_marker_instance(forms[j%7],{x+21,y-5},sty,4));
    text(out,x+54,y,s["name"].GetString(),18);
  }
  for(rapidjson::SizeType i=0;i<doc["panels"].Size();++i) {
    const auto& panel=doc["panels"][i];const double x=(i%columns)*cell+88,y=header+(i/columns)*panel_height+50;
    double maximum=0;
    for(const auto& series:panel["series"].GetArray())for(const auto& p:series["points"].GetArray())maximum=std::max(maximum,p["y"].GetDouble());
    maximum=panel.HasMember("y_max")?panel["y_max"].GetDouble():ceiling(maximum*1.08);
    if(maximum<=0)throw std::runtime_error("invalid y domain");
    // This Izzi revision's range helper takes int coordinates. Normalize only
    // rendering Y values to a safe 1e8 domain so fractional shares and scaled
    // weights survive the helper without truncating to whole percentage points.
    // Original measurements remain in JSON, axes and marker tooltips.
    const point_2t xrange={doc["xmin"].GetDouble(),doc["xmax"].GetDouble()},yrange={0,100000000};
    text(out,x,y-25,panel["title"].GetString(),21);
    const bool percent=panel["unit"]=="percent";
    const style axis={svg::color::none,0,svg::color::black,1,1};
    const style grid={svg::color::none,0,svg::color::gray10,1,0.6};
    out.add_element(make_line({x,y},{x,y+plot_height},axis));out.add_element(make_line({x,y+plot_height},{x+plot_width,y+plot_height},axis));
    for(int tick=0;tick<=5;++tick) {
      const double value=maximum*tick/5,yy=y+plot_height-plot_height*tick/5;
      if(tick)out.add_element(make_line({x,yy},{x+plot_width,yy},grid));
      text(out,x-10,yy+5,label(value,percent),16,"end");
    }
    for(const auto& tick:doc["ticks"].GetArray()) {
      const double xx=x+plot_width*(tick[0].GetDouble()-std::get<0>(xrange))/(std::get<1>(xrange)-std::get<0>(xrange));
      out.add_element(make_line({xx,y+plot_height},{xx,y+plot_height+5},axis));text(out,xx,y+plot_height+27,tick[1].GetString(),16,"middle");
    }
    text(out,x+plot_width/2,y+plot_height+57,doc["xlabel"].GetString(),17,"middle");
    out.add_raw("<g transform=\"translate("+number(x-67)+" "+number(y+plot_height/2)+") rotate(-90)\">");
    text(out,0,0,panel["ylabel"].GetString(),17,"middle");out.add_raw("</g>");
    for(rapidjson::SizeType j=0;j<panel["series"].Size();++j) {
      const auto& s=panel["series"][j];const string id="panel-"+std::to_string(i)+"-series-"+std::to_string(j);
      style sty={parse_color(s["color"].GetString()),1,parse_color(s["color"].GetString()),1,2};
      style line_style=sty;line_style._M_fill_opacity=0;
      graph_rstate state{select::vector,id,{plot_width+400,plot_height+400},chart_line_style_1,"Weeks",panel["ylabel"].GetString(),"","",sty,
                         {"",marker_shape::none,0,s["dash"].GetString(),"","round",""},{0,0},"",""};
      state.lstyle=line_style;
      vrange points;
      for(const auto& p:s["points"].GetArray())points.push_back({p["x"].GetDouble(),p["y"].GetDouble()/maximum*100000000});
      if(points.empty())continue;
      for(std::size_t n=1;n<points.size();++n)if(std::get<0>(points[n])<=std::get<0>(points[n-1]))throw std::runtime_error("unordered weekly points");
      out.add_raw("<g data-series=\""+escape_xml_attribute(s["name"].GetString())+"\" transform=\"translate("+number(x-200)+" "+number(y-200)+")\">");
      // Split at missing intervals so an interior gap never gets interpolated.
      vrange segment;
      auto flush=[&](){if(!segment.empty()){out.add_element(make_line_graph(segment,state,xrange,yrange,4));segment.clear();}};
      for(const auto& p:points){if(!segment.empty()&&std::get<0>(p)-std::get<0>(segment.back())>1.001)flush();segment.push_back(p);}flush();
      const auto positions=transform_to_graph_points(points,state,xrange,yrange);
      for(std::size_t n=0;n<points.size();++n)out.add_raw(make_marker_instance(forms[j%7],positions[n],sty,4,s["points"][n]["tooltip"].GetString()));
      out.add_raw("</g>");
    }
  }
  text(out,25,height-10,"Izzi native weekly line graphs · missing intervals are unplotted · exact values in the accompanying ledger",15);
}
