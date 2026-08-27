"""Iceberg Gold tablolarından bağımsız, tarayıcıda açılabilen HTML raporu üretir."""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


def arguments():
    parser = argparse.ArgumentParser(
        description="Iceberg Gold tablolarından HTML analiz raporu oluşturur."
    )
    parser.add_argument("--warehouse", required=True, help="Iceberg warehouse klasörü")
    parser.add_argument("--output", required=True, help="Yeni oluşturulacak HTML rapor dosyası")
    parser.add_argument("--namespace", default="flight", help="Iceberg namespace (varsayılan: flight)")
    return parser.parse_args()


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def rows_as_dicts(dataframe):
    return [
        {name: json_value(value) for name, value in row.asDict().items()}
        for row in dataframe.collect()
    ]


def report_html(report_data):
    embedded_data = json.dumps(report_data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Flight Data Pipeline · Iceberg Analiz Raporu</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif; }}
    body {{ background:#0b1220; color:#e5edf8; margin:0; padding:32px; }}
    main {{ max-width:1200px; margin:auto; }}
    h1 {{ margin:0 0 8px; }} .muted {{ color:#9fb0c8; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin:24px 0; }}
    .card,.panel {{ background:#121c2d; border:1px solid #24344e; border-radius:12px; padding:18px; }}
    .number {{ font-size:30px; font-weight:700; margin-top:8px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:16px; }}
    .panel h2 {{ font-size:17px; margin:0 0 14px; }}
    svg {{ width:100%; min-height:310px; overflow:visible; }}
    .table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ text-align:left; padding:10px; border-bottom:1px solid #24344e; }}
    th {{ color:#9fb0c8; }} .footer {{ margin-top:22px; font-size:13px; }}
  </style>
</head>
<body><main>
  <h1>Iceberg Analiz Raporu</h1>
  <p class="muted">Kaynak: local.flight Gold tabloları · Üretim zamanı: <span id="generated"></span></p>
  <section class="cards" id="cards"></section>
  <section class="grid">
    <article class="panel"><h2>Saatlik Silver konum olayı</h2><svg id="hourly-events-chart" viewBox="0 0 560 280"></svg></article>
    <article class="panel"><h2>Saatlik benzersiz uçak</h2><svg id="hourly-aircraft-chart" viewBox="0 0 560 280"></svg></article>
    <article class="panel"><h2>Saatlik havada olma oranı</h2><svg id="airborne-rate-chart" viewBox="0 0 560 280"></svg></article>
    <article class="panel"><h2>En yoğun 10 kaynak ülke</h2><svg id="country-chart" viewBox="0 0 560 280"></svg></article>
  </section>
  <section class="panel" style="margin-top:16px"><h2>Silver veri kalitesi</h2><table class="table"><thead><tr><th>Durum</th><th>Neden</th><th>Event sayısı</th></tr></thead><tbody id="quality-table"></tbody></table></section>
  <p class="muted footer">Bu statik rapor Spark'ın Iceberg Gold tablolarını okumasıyla üretildi. Canlı Kafka/MongoDB akışına yazmaz.</p>
</main>
<script>
const report = {embedded_data};
document.querySelector('#generated').textContent = report.generated_at;
const cards = [
  ['Bronze event', report.counts.bronze_positions],
  ['Silver event', report.counts.silver_positions],
  ['Silver red', report.counts.silver_rejected_positions],
  ['Silver kabul oranı', report.acceptance_rate + '%'],
  ['En yoğun saat', report.summary.peak_hour_label],
  ['Zirve saatte uçak', report.summary.peak_hour_aircraft.toLocaleString('tr-TR')],
  ['Havada olma oranı', report.summary.airborne_rate_pct + '%'],
];
document.querySelector('#cards').innerHTML = cards.map(([label,value]) => `<article class="card"><div class="muted">${{label}}</div><div class="number">${{value}}</div></article>`).join('');
const svgNs='http://www.w3.org/2000/svg';
function node(name, attributes={{}}) {{ const item=document.createElementNS(svgNs,name); Object.entries(attributes).forEach(([key,value])=>item.setAttribute(key,value)); return item; }}
function text(svg, x, y, value, anchor='start', size=11, fill='#9fb0c8') {{ const item=node('text',{{x,y,fill,'font-size':size,'text-anchor':anchor}}); item.textContent=value; svg.appendChild(item); return item; }}
function number(value, suffix='') {{ return Number(value).toLocaleString('tr-TR',{{maximumFractionDigits: value % 1 ? 1 : 0}})+suffix; }}
function hourLabel(value) {{ return value.slice(8,10)+'.'+value.slice(5,7)+' '+value.slice(11,16); }}
function line(id, data, valueKey, color, yTitle, options={{}}) {{
  const svg=document.querySelector(id), width=560, height=310, left=62, right=22, top=28, bottom=54;
  const chartWidth=width-left-right, chartHeight=height-top-bottom, values=data.map(row=>Number(row[valueKey]));
  const rawMin=Math.min(...values), rawMax=Math.max(...values);
  let yMin=options.minimum ?? 0, yMax=rawMax;
  if (options.dynamicDomain) {{ const span=Math.max(rawMax-rawMin, 1); yMin=Math.max(0,rawMin-span*.2); yMax=rawMax+span*.2; }}
  yMax=Math.max(yMax, yMin+1);
  const y=value=>top+(yMax-value)*chartHeight/(yMax-yMin), x=index=>left+index*(data.length===1?0:chartWidth/(data.length-1));
  for (let tick=0; tick<=4; tick++) {{ const value=yMin+(yMax-yMin)*tick/4, position=y(value); svg.appendChild(node('line',{{x1:left,y1:position,x2:width-right,y2:position,stroke:'#24344e','stroke-width':1}})); text(svg,left-8,position+4,number(value,options.suffix||''),'end'); }}
  svg.appendChild(node('line',{{x1:left,y1:top,x2:left,y2:height-bottom,stroke:'#7b8ca8'}}));
  svg.appendChild(node('line',{{x1:left,y1:height-bottom,x2:width-right,y2:height-bottom,stroke:'#7b8ca8'}}));
  const labelEvery=Math.max(1,Math.ceil((data.length-1)/4));
  data.forEach((row,index)=>{{ if (index===0 || index===data.length-1 || index%labelEvery===0) {{ const position=x(index); svg.appendChild(node('line',{{x1:position,y1:height-bottom,x2:position,y2:height-bottom+5,stroke:'#7b8ca8'}})); text(svg,position,height-bottom+19,hourLabel(row.hour),'middle'); }} }});
  const points=data.map((row,index)=>`${{x(index)}},${{y(Number(row[valueKey]))}}`).join(' ');
  svg.appendChild(node('polyline',{{points,fill:'none',stroke:color,'stroke-width':3,'stroke-linejoin':'round','stroke-linecap':'round'}}));
  data.forEach((row,index)=>{{ const dot=node('circle',{{cx:x(index),cy:y(Number(row[valueKey])),r:3.5,fill:color,stroke:'#0b1220','stroke-width':1.5}}); const title=node('title'); title.textContent=hourLabel(row.hour)+': '+number(row[valueKey],options.suffix||''); dot.appendChild(title); svg.appendChild(dot); }});
  text(svg,left,15,yTitle,'start',12,'#cbd5e1'); text(svg,width-right,height-8,'Zaman (UTC)','end',11,'#cbd5e1');
}}
function bars(id, data, labelKey, valueKey, color) {{
  const svg=document.querySelector(id), width=560, height=310, left=164, right=56, top=28, bottom=38, chartWidth=width-left-right, chartHeight=height-top-bottom;
  const max=Math.max(...data.map(row=>Number(row[valueKey])),1), x=value=>left+value*chartWidth/max;
  for (let tick=0; tick<=4; tick++) {{ const value=max*tick/4, position=x(value); svg.appendChild(node('line',{{x1:position,y1:top,x2:position,y2:height-bottom,stroke:'#24344e','stroke-width':1}})); text(svg,position,height-bottom+18,number(value),'middle'); }}
  data.forEach((row,index)=>{{ const rowHeight=chartHeight/data.length, y=top+index*rowHeight+4, barHeight=Math.max(9,rowHeight-7), value=Number(row[valueKey]); svg.appendChild(node('rect',{{x:left,y,width:x(value)-left,height:barHeight,rx:4,fill:color}})); text(svg,left-8,y+barHeight-1,row[labelKey],'end'); text(svg,x(value)+7,y+barHeight-1,number(value)); }});
  text(svg,left,15,'Konum olayı','start',12,'#cbd5e1'); text(svg,width-right,height-8,'Event sayısı','end',11,'#cbd5e1');
}}
line('#hourly-events-chart', report.hourly_activity, 'position_events', '#38bdf8', 'Konum olayı');
line('#hourly-aircraft-chart', report.hourly_activity, 'unique_aircraft', '#34d399', 'Benzersiz uçak');
line('#airborne-rate-chart', report.hourly_activity, 'airborne_rate_pct', '#fbbf24', 'Havada olma oranı', {{suffix:'%',dynamicDomain:true}});
bars('#country-chart', report.countries, 'origin_country', 'position_events', '#a78bfa');
document.querySelector('#quality-table').innerHTML=report.quality.map(row=>`<tr><td>${{row.quality_status}}</td><td>${{row.quality_reason || '—'}}</td><td>${{row.count.toLocaleString('tr-TR')}}</td></tr>`).join('');
</script></body></html>"""


def main():
    args = arguments()
    output = Path(args.output)
    if output.exists():
        raise ValueError(f"Rapor dosyası zaten var: {output}")
    if not Path(args.warehouse).is_dir():
        raise ValueError(f"Iceberg warehouse bulunamadı: {args.warehouse}")

    spark = (
        SparkSession.builder.appName("flight-iceberg-html-report")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", args.warehouse)
        .config("spark.sql.defaultCatalog", "local")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        prefix = f"local.{args.namespace}"
        counts = {
            table: spark.table(f"{prefix}.{table}").count()
            for table in ("bronze_positions", "silver_positions", "silver_rejected_positions")
        }
        hourly = rows_as_dicts(
            spark.table(f"{prefix}.gold_hourly_traffic")
            .groupBy("hour")
            .agg(F.sum("position_events").alias("position_events"))
            .orderBy("hour")
        )
        hourly_activity = rows_as_dicts(
            spark.table(f"{prefix}.gold_hourly_activity").orderBy("hour")
        )
        countries = rows_as_dicts(
            spark.table(f"{prefix}.gold_hourly_traffic")
            .groupBy("origin_country")
            .agg(F.sum("position_events").alias("position_events"))
            .orderBy(F.desc("position_events"), "origin_country")
            .limit(10)
        )
        quality = rows_as_dicts(
            spark.table(f"{prefix}.gold_data_quality")
            .orderBy("quality_status", F.desc("count"), "quality_reason")
        )
        acceptance_rate = round(
            100 * counts["silver_positions"] / max(counts["bronze_positions"], 1), 2
        )
        peak_hour = max(hourly_activity, key=lambda row: row["position_events"])
        total_events = sum(row["position_events"] for row in hourly_activity)
        total_airborne = sum(row["airborne_events"] for row in hourly_activity)
        peak_hour_label = datetime.fromisoformat(peak_hour["hour"]).strftime(
            "%d.%m %H:%M UTC"
        )
        report_data = {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "counts": counts,
            "acceptance_rate": acceptance_rate,
            "hourly": hourly,
            "hourly_activity": hourly_activity,
            "countries": countries,
            "quality": quality,
            "summary": {
                "peak_hour_label": peak_hour_label,
                "peak_hour_aircraft": peak_hour["unique_aircraft"],
                "airborne_rate_pct": round(100 * total_airborne / max(total_events, 1), 2),
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_html(report_data), encoding="utf-8")
        print(f"HTML Iceberg raporu oluşturuldu: {output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
