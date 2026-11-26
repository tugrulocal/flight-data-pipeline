#!/usr/bin/env python3
"""Flight Data Pipeline staj sunumunu düzenlenebilir PowerPoint olarak üretir."""

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt


OUT = Path("deliverables/flight-data-pipeline-staj-sunumu-final-rc5-platform.pptx")
P = Presentation()
P.slide_width = Inches(13.333)
P.slide_height = Inches(7.5)

NAVY = "102A43"
BLUE = "1976D2"
CYAN = "00ACC1"
GREEN = "2E7D32"
ORANGE = "EF6C00"
RED = "C62828"
PURPLE = "6A1B9A"
GREY = "5B6770"
LIGHT = "F5F8FB"
DARK = "172B4D"
WHITE = "FFFFFF"


def rgb(value):
    return RGBColor.from_string(value)


def rect(slide, x, y, w, h, color=WHITE, radius=False, line=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)
    shape.line.color.rgb = rgb(line or color)
    return shape


def text(slide, value, x, y, w, h, size=18, color=DARK, bold=False,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, font="Aptos", margin=0.08):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return box


def title(slide, heading, subtitle=None, number=None):
    rect(slide, 0, 0, 13.333, 0.18, BLUE)
    text(slide, heading, 0.62, 0.36, 11.5, 0.52, 26, NAVY, True)
    if subtitle:
        text(slide, subtitle, 0.64, 0.93, 11.5, 0.34, 11, GREY)
    if number:
        text(slide, f"{number:02d}", 12.15, 0.37, 0.55, 0.36, 12, BLUE, True, PP_ALIGN.RIGHT)
    rect(slide, 0.62, 7.1, 12.1, 0.01, "D9E2EC")
    text(slide, "Flight Data Pipeline • Staj Projesi", 0.62, 7.17, 5.3, 0.18, 8, GREY)


def bullets(slide, items, x, y, w, h, size=17, color=DARK, bullet_color=BLUE):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    for index, item in enumerate(items):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        p.level = 0
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.color.rgb = rgb(color)
        p.space_after = Pt(11)
    return box


def card(slide, heading, body, x, y, w, h, accent=BLUE):
    rect(slide, x, y, w, h, LIGHT, True, "D9E2EC")
    rect(slide, x, y, 0.08, h, accent)
    if h < 1.2:
        text(slide, heading, x + 0.22, y + 0.12, w - 0.34, 0.22, 12, NAVY, True)
        text(slide, body, x + 0.22, y + 0.4, w - 0.36, h - 0.47, 9, GREY)
        return
    text(slide, heading, x + 0.25, y + 0.18, w - 0.4, 0.35, 15, NAVY, True)
    text(slide, body, x + 0.25, y + 0.63, w - 0.42, h - 0.76, 12, GREY)


def arrow(slide, x1, y1, x2, y2, color=BLUE, width=2):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = rgb(color)
    line.line.width = Pt(width)
    line.line.end_arrowhead = True
    return line


def node(slide, label, x, y, w, h, color=BLUE, note=None):
    rect(slide, x, y, w, h, color, True, color)
    text(slide, label, x + 0.08, y + 0.12, w - 0.16, h * 0.48, 14, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    if note:
        text(slide, note, x + 0.08, y + h * 0.56, w - 0.16, h * 0.32, 9, WHITE, False, PP_ALIGN.CENTER)


def agenda_slide():
    s = P.slides.add_slide(P.slide_layouts[6])
    title(s, "Sunum akışı", "15–20 dakika anlatım + 3–4 dakika canlı demo", 2)
    agenda = [
        ("1", "Problem ve hedef"), ("2", "Canlı veri mimarisi"),
        ("3", "Güvenilirlik ve hata yönetimi"), ("4", "Kullanıcı arayüzü"),
        ("5", "DevOps, Kubernetes ve izleme"), ("6", "Spark / Iceberg analitik katmanı"),
        ("7", "Test, release ve sonraki adımlar"),
    ]
    for i, (n, label) in enumerate(agenda):
        col, row = i % 2, i // 2
        x, y = 0.95 + col * 6.1, 1.55 + row * 1.25
        rect(s, x, y, 5.55, 0.9, LIGHT, True, "D9E2EC")
        rect(s, x + 0.18, y + 0.17, 0.54, 0.54, BLUE if i < 4 else PURPLE, True)
        text(s, n, x + 0.18, y + 0.24, 0.54, 0.25, 13, WHITE, True, PP_ALIGN.CENTER)
        text(s, label, x + 0.9, y + 0.25, 4.3, 0.3, 18, NAVY, True)
    return s


def add_content():
    # 1 Cover
    s = P.slides.add_slide(P.slide_layouts[6])
    rect(s, 0, 0, 13.333, 7.5, NAVY)
    rect(s, 0, 0, 13.333, 0.18, CYAN)
    text(s, "Flight Data Pipeline", 0.75, 1.25, 8.8, 0.72, 34, WHITE, True)
    text(s, "Canlı uçuş verisinden güvenilir veri hattına, yerel Kubernetes cluster'a,\nweb arayüzüne ve analitik katmana", 0.78, 2.15, 9.2, 1.0, 21, "D9EAF7")
    text(s, "Staj Projesi Sunumu · Güncel sürüm: v1.0.0-rc.5", 0.8, 3.55, 6.7, 0.35, 16, CYAN, True)
    text(s, "OpenSky • Kafka • MongoDB • FastAPI • React • Docker • Kubernetes • Spark • Iceberg", 0.8, 4.1, 10.6, 0.3, 13, WHITE)
    for i, (lab, col) in enumerate([("API", CYAN), ("STREAM", BLUE), ("DB", GREEN), ("WEB", ORANGE), ("ANALYTICS", PURPLE)]):
        node(s, lab, 0.8 + i * 2.25, 5.45, 1.85, 0.72, col)
        if i:
            arrow(s, 0.8 + i * 2.25 - 0.3, 5.81, 0.8 + i * 2.25, 5.81, "8FA7BF")

    agenda_slide()

    # 3 Problem
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "Başlangıç problemi", "Canlı dış veriyi kullanıcıya doğrudan bağlamak yeterli değildir.", 3)
    card(s, "Dış kaynak değişken", "OpenSky API gecikebilir, kota uygulayabilir veya geçici olarak yanıt vermeyebilir.", 0.75, 1.55, 3.8, 2.15, ORANGE)
    card(s, "Canlı ekran hassas", "Kullanıcı haritayı açtığında güncel bir durum görmeli; bağlantı koparsa toparlanmalıdır.", 4.77, 1.55, 3.8, 2.15, BLUE)
    card(s, "Veri kaybı riski", "Bir servis çökerken mesajı kaybetmeden, tekrar işlese bile çift kayıt üretmeden devam etmeliyiz.", 8.78, 1.55, 3.8, 2.15, RED)
    text(s, "Çözüm yaklaşımı", 0.78, 4.45, 2.4, 0.35, 20, NAVY, True)
    bullets(s, ["Canlı veri ile kalıcı veriyi ayırmak", "Servisleri mesaj kuyruğu ile gevşek bağlamak", "Hataları görünür ve tekrar işlenebilir kılmak", "Kullanıcıya REST + WebSocket ile kontrollü veri sunmak"], 0.85, 4.95, 10.8, 1.65, 17)

    # 4 Goals
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "Proje hedefleri", "Tek hedef ekran yapmak değil; uçtan uca veri mühendisliği pratiği kazanmaktı.", 4)
    card(s, "Ürün hedefi", "Canlı uçak listesi, konum haritası, seçili uçağın rotası ve geçmiş sorgusu.", 0.8, 1.45, 5.65, 1.55, BLUE)
    card(s, "Öğrenme hedefi", "Docker, Kafka, MongoDB, FastAPI, React, test, release ve operasyon kavramlarını birlikte uygulamak.", 6.85, 1.45, 5.65, 1.55, GREEN)
    card(s, "Kalite hedefi", "Veri kaybına dayanıklılık, idempotent yazım, hata izolasyonu, doğrulanabilir kurulum ve geri alma yolu.", 0.8, 3.45, 5.65, 1.55, ORANGE)
    card(s, "Analitik hedef", "Ham olaylardan Spark ile Bronze / Silver / Gold katmanları ve Iceberg snapshot yönetimi oluşturmak.", 6.85, 3.45, 5.65, 1.55, PURPLE)
    text(s, "Başarı ölçütü: Kodun çalışması + gözlemlenebilirlik + test kanıtı + güvenli işletim.", 0.86, 5.7, 11.4, 0.45, 18, NAVY, True, PP_ALIGN.CENTER)

    # 5 architecture
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "Canlı veri hattı: büyük resim", "Veri kaynağından kullanıcı ekranına kadar sorumluluklar ayrılmıştır.", 5)
    node(s, "OpenSky", 0.5, 2.55, 1.45, 0.95, CYAN, "REST API")
    node(s, "Producer", 2.35, 2.55, 1.55, 0.95, BLUE, "Python")
    node(s, "Kafka", 4.35, 2.55, 1.55, 0.95, ORANGE, "raw topic")
    node(s, "MongoDB\nConsumer", 6.35, 1.5, 1.75, 0.95, GREEN, "kalıcı yazım")
    node(s, "FastAPI", 6.35, 3.65, 1.75, 0.95, PURPLE, "REST + WS")
    node(s, "MongoDB", 8.6, 1.5, 1.55, 0.95, GREEN, "raw + live")
    node(s, "React", 10.65, 3.65, 1.55, 0.95, BLUE, "harita")
    arrow(s, 1.95, 3.03, 2.35, 3.03); arrow(s, 3.9, 3.03, 4.35, 3.03)
    arrow(s, 5.9, 2.85, 6.35, 2.0); arrow(s, 5.9, 3.2, 6.35, 4.13)
    arrow(s, 8.1, 1.98, 8.6, 1.98); arrow(s, 8.1, 4.13, 10.65, 4.13)
    arrow(s, 9.38, 2.45, 8.1, 4.0, GREEN)
    text(s, "İki ayrı tüketici grubu aynı mesajları bağımsız okur; biri veritabanına yazar, diğeri canlı yayın yapar.", 0.78, 5.55, 11.8, 0.55, 17, NAVY, True, PP_ALIGN.CENTER)

    # 6 Producer
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "1. Veri üretimi: OpenSky Producer", "Dış API yanıtını ortak bir olay sözleşmesine dönüştüren Python servisi.", 6)
    bullets(s, ["OpenSky REST API’den uçak konumlarını periyodik olarak alır.", "Global veya Türkiye + yakın çevre bounding-box modunda çalışabilir.", "Her olaya schema_version ve benzersiz event_id ekler.", "Kimlik bilgileri ve çalışma ayarları kodda değil, ortam değişkenlerinde tutulur.", "Rate-limit bilgisine göre bekler; anonim kullanımda güvenli minimum sorgu aralığı uygular."], 0.75, 1.45, 6.4, 4.5, 16)
    card(s, "Neden event_id?", "Mesaj yeniden işlenirse aynı gerçek olayı yeniden tanıyabilmek için kalıcı kimlik gerekir.", 7.65, 1.55, 4.6, 1.45, BLUE)
    card(s, "Hata halinde", "API geçici yanıt vermezse producer kontrollü yeniden dener; Kafka zaten almış mesajlar kaybolmaz.", 7.65, 3.3, 4.6, 1.45, ORANGE)
    card(s, "Doğrulama", "Producer loglarında poll sayısı / gönderilen mesaj; Kafka topic’inde yeni kayıtlar izlenir.", 7.65, 5.05, 4.6, 1.1, GREEN)

    # 7 kafka
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "2. Kafka: veri hattının omurgası", "Kafka, üretici ile tüketicileri birbirinden bağımsız çalıştıran kalıcı mesaj katmanıdır.", 7)
    node(s, "Producer", 0.8, 2.6, 1.8, 1.0, BLUE, "üretir")
    node(s, "aircraft.positions\n.raw.v1", 4.1, 2.45, 2.4, 1.3, ORANGE, "Kafka topic")
    node(s, "Mongo writer\ngroup", 8.0, 1.45, 1.85, 1.0, GREEN, "tüm mesajlar")
    node(s, "Realtime gateway\ngroup", 8.0, 3.85, 1.85, 1.0, PURPLE, "tüm mesajlar")
    arrow(s, 2.6, 3.1, 4.1, 3.1); arrow(s, 6.5, 2.88, 8.0, 1.96); arrow(s, 6.5, 3.32, 8.0, 4.34)
    card(s, "Önemli ayrım", "Aynı consumer group olsalardı mesajları paylaşırlar ve iki işlevin de her mesajı görmesi garanti olmazdı.", 0.8, 5.35, 10.7, 0.95, RED)
    text(s, "Ayrı group → aynı olayın iki farklı iş amacı için bağımsız okunması", 1.1, 6.45, 10.8, 0.3, 16, NAVY, True, PP_ALIGN.CENTER)

    # 8 Mongo
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "3. MongoDB: geçmiş ve canlı durum ayrımı", "Tek koleksiyonla hem arşiv hem ekran performansı hedeflenmedi.", 8)
    card(s, "raw_positions", "Her Kafka olayının tarihçesi\n• _id = event_id\n• rota / analiz / hata inceleme\n• index: icao24 + observed_at\n• 48 saat TTL", 0.9, 1.6, 5.25, 3.2, GREEN)
    card(s, "live_positions", "Her uçak için son durum\n• _id = icao24\n• frontend ilk snapshot kaynağı\n• hızlı canlı liste sorgusu\n• 7 gün TTL", 7.15, 1.6, 5.25, 3.2, BLUE)
    arrow(s, 6.15, 3.15, 7.15, 3.15, "8FA7BF")
    text(s, "Ham olay = analiz ve geçmiş • Son durum = canlı kullanıcı deneyimi", 1.1, 5.55, 11.0, 0.45, 19, NAVY, True, PP_ALIGN.CENTER)

    # 9 delivery
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "4. Teslim garantisi: neden veri kaybolmuyor?", "Tasarım: at-least-once teslim + idempotent MongoDB yazımı.", 9)
    steps = [("1", "Kafka mesajı alınır", BLUE), ("2", "raw_positions upsert", GREEN), ("3", "live_positions upsert", GREEN), ("4", "Offset commit", ORANGE)]
    for i, (n, lab, col) in enumerate(steps):
        x = 0.65 + i * 3.12
        rect(s, x, 2.05, 2.55, 1.25, LIGHT, True, "D9E2EC")
        rect(s, x + 0.14, 2.31, 0.55, 0.55, col, True)
        text(s, n, x + 0.14, 2.43, 0.55, 0.22, 13, WHITE, True, PP_ALIGN.CENTER)
        text(s, lab, x + 0.85, 2.4, 1.5, 0.35, 14, NAVY, True, PP_ALIGN.CENTER)
        if i < 3: arrow(s, x + 2.55, 2.68, x + 3.12, 2.68)
    card(s, "Çökme örneği", "MongoDB yazımından sonra fakat offset commit’ten önce süreç çökerse Kafka mesajı yeniden gönderir.", 0.95, 4.1, 5.45, 1.35, ORANGE)
    card(s, "Tekrarın güvenliği", "event_id ile yapılan upsert, aynı Kafka mesajının ikinci kez ayrı raw belge yaratmasını önler.", 6.85, 4.1, 5.45, 1.35, GREEN)
    text(s, "Bu, uçtan uca exactly-once değildir; fakat pratikte veri kaybı ve duplicate riskini yönetir.", 1.0, 6.05, 11.3, 0.35, 16, RED, True, PP_ALIGN.CENTER)

    # 10 DLQ retry
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "5. Bozuk mesaj ve geçici hata yönetimi", "Ana akışın durmaması, hatanın görünmez olması anlamına gelmez.", 10)
    node(s, "Geçerli mesaj", 0.8, 2.25, 1.8, 0.9, GREEN)
    node(s, "MongoDB yazımı", 3.4, 2.25, 1.9, 0.9, BLUE)
    node(s, "Başarılı\ncommit", 6.2, 1.2, 1.7, 0.9, GREEN)
    node(s, "Geçici hata\nretry", 6.2, 3.3, 1.7, 0.9, ORANGE)
    node(s, "Kalıcı bozuk\nDLQ", 9.0, 3.3, 1.7, 0.9, RED)
    arrow(s, 2.6, 2.7, 3.4, 2.7); arrow(s, 5.3, 2.45, 6.2, 1.65); arrow(s, 5.3, 2.95, 6.2, 3.75); arrow(s, 7.9, 3.75, 9.0, 3.75)
    bullets(s, ["Geçici MongoDB hatalarında sınırlı exponential backoff ile retry yapılır.", "Kalıcı biçimde bozuk mesajlar Base64 kaynak zarfıyla DLQ topic’ine taşınır.", "DLQ teslimi doğrulanmadan ana offset ilerletilmez.", "DLQ operasyonel olarak izlenmelidir; hata saklanmaz, ayrıştırılır."], 0.9, 5.15, 11.2, 1.25, 14)

    # 11 backend
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "6. FastAPI: frontend için güvenli geçit", "Tarayıcı Kafka’ya veya MongoDB’ye doğrudan bağlanmaz.", 11)
    node(s, "MongoDB", 0.85, 2.15, 1.8, 0.9, GREEN, "snapshot + history")
    node(s, "Kafka", 0.85, 4.2, 1.8, 0.9, ORANGE, "realtime group")
    node(s, "FastAPI", 4.5, 3.15, 2.1, 1.15, PURPLE, "REST + WebSocket")
    node(s, "React / Nginx", 9.15, 3.15, 2.1, 1.15, BLUE, "tarayıcı")
    arrow(s, 2.65, 2.6, 4.5, 3.58); arrow(s, 2.65, 4.65, 4.5, 3.85); arrow(s, 6.6, 3.72, 9.15, 3.72)
    card(s, "REST", "/health, /api/aircraft, tek uçak, geçmiş, istatistik. İlk açılıştaki güvenilir durum kaynağıdır.", 0.8, 5.55, 5.35, 0.95, BLUE)
    card(s, "WebSocket", "/ws/aircraft. Yeni uçak konumlarını anlık iter; bağlantı sonrası REST ile yeniden eşitlenir.", 6.85, 5.55, 5.35, 0.95, PURPLE)

    # 12 Frontend
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "7. React frontend: canlı, anlaşılır ve dayanıklı", "Kullanıcının gördüğü ekran, gerçek zamanlı veri hattının son adımıdır.", 12)
    card(s, "Canlı harita", "MapLibre varsayılan motor. Uçak sembolleri uçuş yönüne göre döner; irtifa renkleri yüksek kontrastlıdır.", 0.75, 1.45, 3.8, 2.05, BLUE)
    card(s, "Geçmiş rota", "Uçağa tıklanınca raw_positions üzerinden geçmiş noktalar okunur; rota irtifa aralığına göre renklidir.", 4.78, 1.45, 3.8, 2.05, GREEN)
    card(s, "Uyumluluk", "WebGL ya da yükleme hatasında Leaflet otomatik fallback olur; kullanıcıya yeniden deneme seçeneği sunulur.", 8.8, 1.45, 3.8, 2.05, ORANGE)
    bullets(s, ["Sadece son 20 dakika içinde gözlenen uçaklar canlı ekranda gösterilir.", "WebSocket mesajları requestAnimationFrame ile toplu uygulanır; her mesaj ayrı render yaratmaz.", "Nginx aynı-origin proxy ile REST ve WebSocket’i frontend üzerinden güvenli biçimde iletir."], 0.9, 4.2, 11.2, 1.7, 16)

    # 13 Docker
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "8. Docker Compose: taşınabilir yerel sistem", "Her bileşen ayrı container; bütün sistem tek Compose tanımıyla ayağa kalkar.", 13)
    components = [("kafka-volume-init", RED), ("Kafka", ORANGE), ("topic-init", ORANGE), ("MongoDB", GREEN), ("producer", BLUE), ("consumer", GREEN), ("backend", PURPLE), ("frontend", BLUE)]
    for i, (lab, col) in enumerate(components):
        x, y = 0.8 + (i % 4) * 3.05, 1.55 + (i // 4) * 1.35
        node(s, lab, x, y, 2.45, 0.8, col)
    card(s, "Kalıcı veri", "Kafka ve MongoDB named volume kullanır. Normal docker compose down veriyi korur; down -v veri siler.", 0.8, 4.6, 5.4, 1.25, GREEN)
    card(s, "Ağ yüzeyi", "Release Compose yalnız frontend’i 127.0.0.1:5175 üzerinde host’a açar. Backend/Kafka/Mongo iç ağda kalır.", 6.85, 4.6, 5.4, 1.25, BLUE)
    text(s, "Temiz Kafka volume’larda izin sorununu çözmek için kafka-volume-init, broker başlatılmadan yalnız volume sahibini düzeltir.", 0.85, 6.25, 11.5, 0.38, 14, NAVY, True, PP_ALIGN.CENTER)

    # 14 Kubernetes
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "9. Kubernetes öğrenme yolu ve GitOps", "Yerelde çalışan yapı, Kubernetes kaynaklarına aşamalı olarak taşındı.", 14)
    lessons = [("01", "MongoDB + temel servisler"), ("02", "Kafka + topic init"), ("03", "Producer + Consumer"), ("04", "Backend + Frontend + Ingress"), ("05", "Tam sistem + izleme")]
    for i, (num, lab) in enumerate(lessons):
        x = 0.65 + i * 2.55
        rect(s, x, 2.0, 2.05, 1.55, LIGHT, True, "D9E2EC")
        rect(s, x + 0.73, 1.72, 0.6, 0.6, PURPLE, True)
        text(s, num, x + 0.73, 1.85, 0.6, 0.22, 12, WHITE, True, PP_ALIGN.CENTER)
        text(s, lab, x + 0.18, 2.48, 1.7, 0.55, 12, NAVY, True, PP_ALIGN.CENTER)
        if i < 4: arrow(s, x + 2.05, 2.78, x + 2.55, 2.78, "8FA7BF")
    card(s, "Deployment", "Producer, consumer, backend ve frontend çökerse Kubernetes yeni pod başlatır.", 0.85, 4.55, 3.6, 1.15, BLUE)
    card(s, "StatefulSet + PVC", "Kafka ve MongoDB yeniden başlasa bile kalıcı diskleri korunur.", 4.85, 4.55, 3.6, 1.15, GREEN)
    card(s, "Argo CD", "Manifestler Git üzerinden izlenir ve cluster’a GitOps yaklaşımıyla uygulanır.", 8.85, 4.55, 3.6, 1.15, PURPLE)

    # 15 Monitoring
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "10. İzleme: sistemin sağlığını görünür kılmak", "Çalışan sistem ile gözlemlenebilir sistem aynı şey değildir.", 15)
    node(s, "Producer", 0.85, 2.55, 1.65, 0.85, BLUE, "metrik")
    node(s, "Backend", 3.2, 2.55, 1.65, 0.85, PURPLE, "metrik")
    node(s, "Prometheus", 5.6, 2.55, 1.9, 0.85, ORANGE, "toplar")
    node(s, "Grafana", 8.3, 2.55, 1.65, 0.85, GREEN, "görselleştirir")
    arrow(s, 2.5, 2.98, 5.6, 2.8); arrow(s, 4.85, 3.12, 5.6, 3.12); arrow(s, 7.5, 2.98, 8.3, 2.98)
    bullets(s, ["Prometheus ve Grafana ayrı monitoring namespace’inde yönetilir.", "Pod hazır olma, CPU/bellek/ağ ve uygulama metrikleri izlenebilir.", "Grafana dashboard değişiklikleri de kod ve Argo CD ile takip edilir.", "/health ile readiness aynı anlamda değildir: uygulama ayakta olabilir, dış bağımlılıkları eksik olabilir."], 0.9, 4.55, 11.3, 1.55, 16)

    # 16 analytics flow
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "11. Analitik katman: canlı hattan bağımsız Spark", "Analiz işini canlı uçuş deneyimini etkilemeden ayrı bir batch yolunda ele aldık.", 16)
    node(s, "MongoDB\nraw_positions", 0.65, 2.55, 1.75, 1.0, GREEN, "salt-okunur")
    node(s, "JSONL.gz\nexport", 3.3, 2.55, 1.65, 1.0, BLUE, "Git dışı")
    node(s, "Spark local[2]", 5.75, 2.55, 1.85, 1.0, ORANGE, "Docker")
    node(s, "Bronze / Silver\n/ Rejected", 8.45, 1.45, 1.9, 1.0, PURPLE, "detay")
    node(s, "Gold\nözetler", 8.45, 3.75, 1.9, 1.0, GREEN, "rapor")
    arrow(s, 2.4, 3.05, 3.3, 3.05); arrow(s, 4.95, 3.05, 5.75, 3.05); arrow(s, 7.6, 2.75, 8.45, 1.95); arrow(s, 7.6, 3.35, 8.45, 4.25)
    text(s, "Önemli sınır: Spark bu aşamada Kafka’yı tüketmez ve MongoDB’ye yazmaz; canlı yol aynen çalışmaya devam eder.", 0.95, 5.7, 11.4, 0.45, 16, RED, True, PP_ALIGN.CENTER)

    # 17 medalion
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "12. Bronze / Silver / Gold: veriyi adım adım olgunlaştırmak", "Her katmanın farklı bir sorumluluğu vardır.", 17)
    card(s, "Bronze — ham ama tiplenmiş", "Dışa aktarılan bütün okunabilir olaylar. Kalite filtresi uygulanmaz; veri kaynağına en yakın katmandır.", 0.75, 1.75, 3.7, 3.35, ORANGE)
    card(s, "Silver — analiz için güvenilir", "Kimlik, zaman, koordinat ve hız kurallarını geçen olaylar. Hatalı / eski gözlemler rejected tablosuna ayrılır.", 4.82, 1.75, 3.7, 3.35, "7B1FA2")
    card(s, "Gold — karar için özet", "Saatlik trafik, aktivite ve veri kalitesi gibi dashboard/rapor dostu sonuçlar yalnız Silver’dan üretilir.", 8.9, 1.75, 3.7, 3.35, GREEN)
    arrow(s, 4.45, 3.42, 4.82, 3.42); arrow(s, 8.52, 3.42, 8.9, 3.42)
    text(s, "Örnek kalite kuralları: negatif veya 400 m/s üzeri hız; observed_at ile ingested_at arasında 20 dakikayı aşan gecikme.", 0.9, 5.8, 11.6, 0.45, 15, NAVY, True, PP_ALIGN.CENTER)

    # 18 Iceberg
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "13. Apache Iceberg: tablo sürümü ve güvenli yenileme", "Iceberg, Parquet dosyalarının üzerinde şema, partition ve snapshot yönetimi sağlar.", 18)
    card(s, "Tablo soyutlaması", "Veri dosyaları Parquet olarak kalır; metadata klasörü şemayı, snapshot’ları ve hangi dosyaların tabloda olduğunu yönetir.", 0.85, 1.5, 5.35, 1.55, PURPLE)
    card(s, "Snapshot / time-travel", "Başarılı append yeni snapshot oluşturur. Güncel tablo normal SQL ile; geçmiş hal VERSION AS OF ile sorgulanabilir.", 6.85, 1.5, 5.35, 1.55, BLUE)
    card(s, "Kontrollü batch refresh", "Önce dry-run; sonra event_id anti-join ile yalnız yeni olaylar Bronze’a append edilir. İki kez ekleme engellenir.", 0.85, 3.65, 5.35, 1.55, GREEN)
    card(s, "Kaynak sınırı", "Tek Docker container içinde Spark local[2], en fazla 2 CPU ve 3 GiB bellek kullanır; Kubernetes kaynaklarını korur.", 6.85, 3.65, 5.35, 1.55, ORANGE)
    text(s, "Amaç: ham veriye dokunmadan, tekrar çalıştırılabilir ve izlenebilir analiz yenilemeleri yapmak.", 0.85, 6.2, 11.6, 0.4, 17, NAVY, True, PP_ALIGN.CENTER)

    # 19 lifecycle
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "14. Test yaklaşımı: her katmanı kanıtlamak", "Bir değişiklik ancak gözlemlenebilir kanıtla tamamlanmış sayılır.", 19)
    rows = [
        ("Kod", "Python syntax, unit test, frontend test/build", BLUE),
        ("Entegrasyon", "İzole Kafka + Mongo: retry, DLQ, lag, TTL, retention, index", GREEN),
        ("Uçtan uca", "REST snapshot, WebSocket, canlı harita, history rotası", PURPLE),
        ("Operasyon", "restart, backup / boş hedef restore, log ve consumer lag", ORANGE),
        ("Release", "çok mimari image, SBOM, provenance, Cosign, offline paket", RED),
    ]
    for i, (h, b, col) in enumerate(rows):
        y = 1.35 + i * 1.05
        rect(s, 0.9, y, 1.7, 0.72, col, True)
        text(s, h, 0.98, y + 0.2, 1.54, 0.23, 14, WHITE, True, PP_ALIGN.CENTER)
        rect(s, 2.85, y, 9.3, 0.72, LIGHT, True, "D9E2EC")
        text(s, b, 3.1, y + 0.18, 8.85, 0.28, 14, NAVY)

    # 20 Release
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "15. Release ve dağıtım disiplini", "Geliştirme ortamında çalışan şey, temiz hedefte de doğrulanmalıdır.", 20)
    bullets(s, ["AMD64 ve ARM64 için image’lar ayrı üretilir; registry’de çok mimarili manifest hedeflenir.", "SBOM (bileşen listesi), provenance (üretim kökeni) ve keyless Cosign imzası release güven zincirinin parçasıdır.", "Offline paket dış/iç SHA-256 doğrulaması, sürümlü Compose ve setup/backup/restore scriptleri içerir.", "Setup scripti mimari, Docker/Compose, bellek, port, disk ve image bütünlüğünü denetler.", "Rollback: APP_VERSION önceki sürüme alınabilir; veri şeması için backup/restore prosedürü ayrıca korunur."], 0.75, 1.4, 7.0, 4.9, 16)
    card(s, "RC.2'den öğrenilen", "Temiz Kafka named volume izin hatası kabulü durdurdu. Sorun saklanmadı; düzeltme tasarıma eklendi.", 8.25, 1.6, 3.9, 1.35, RED)
    card(s, "RC.5 güncel durum", "v1.0.0-rc.5 yayımlandı. Uygulama image'ları Kubernetes manifestlerinde değişmez digest ile pinli.", 8.25, 3.25, 3.9, 1.45, GREEN)
    card(s, "Release ilkesi", "Tag → CI/audit/integration → multi-arch image → SBOM/provenance/Cosign → offline paket → GitOps PR ve Argo CD sync.", 8.25, 5.05, 3.9, 1.15, BLUE)

    # 21 Demo
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "16. Canlı demo planı", "Demo kısa tutulur: ürün değerini ve hattın sağlığını birlikte gösterir.", 21)
    demo = [("1", "Servisler", "docker compose ps ile container health durumunu göster."), ("2", "Kullanıcı ekranı", "Haritayı aç; canlı uçak listesini ve filtrelemeyi göster."), ("3", "Geçmiş rota", "Bir uçağı seç; geçmiş noktaların rota olarak çizildiğini göster."), ("4", "Backend kanıtı", "/health ve /api/aircraft endpoint’lerini göster."), ("5", "Veri hattı", "Mongo raw/live kayıt sayısı ve iki consumer group lag=0 kanıtını göster.")]
    for i, (n, h, b) in enumerate(demo):
        x = 0.7 + (i % 3) * 4.15; y = 1.45 + (i // 3) * 2.25
        card(s, f"{n}. {h}", b, x, y, 3.7, 1.65, BLUE if i < 3 else GREEN)
    text(s, "Demo sırasında hata olursa: log göstermek yerine önce /health, ardından consumer lag ve servis loglarıyla problemi daralt.", 0.9, 6.3, 11.5, 0.35, 15, RED, True, PP_ALIGN.CENTER)

    # 22 lessons
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "17. Staj boyunca ne öğrendim?", "Tek tek araçlardan çok, araçların birlikte oluşturduğu sistem davranışını öğrendim.", 22)
    lessons = [
        ("Sistem tasarımı", "Sorumlulukları ayırmak; veri üretimi, depolama, API ve arayüzü birbirinden bağımsızlaştırmak."),
        ("Dağıtık veri", "Topic, consumer group, offset, lag, yeniden deneme ve idempotency kavramlarını gerçek akışta kullanmak."),
        ("Veri modelleme", "Ham geçmiş ile güncel durum için farklı koleksiyon, index ve TTL stratejileri tasarlamak."),
        ("Ürün geliştirme", "REST snapshot ile WebSocket’in birbirini tamamladığını; fallback ve performansın kullanıcı deneyimini belirlediğini görmek."),
        ("Operasyon", "Container, healthcheck, backup/restore, monitoring, release kanıtı ve güvenli geri alma süreçlerini uygulamak."),
        ("Analitik", "Bronze/Silver/Gold, veri kalitesi, incremental refresh ve Iceberg snapshot/time-travel yaklaşımını uygulamak."),
    ]
    for i, (h, b) in enumerate(lessons):
        x, y = 0.7 + (i % 2) * 6.05, 1.35 + (i // 2) * 1.65
        card(s, h, b, x, y, 5.5, 1.3, [BLUE, GREEN, PURPLE, ORANGE, RED, CYAN][i])

    # 23 current scope
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "18. Güncel durum ve bilinçli sınırlar", "RC.5 ile çalışan bir eğitim/yerel geliştirme sistemi var; production iddiası için ayrı kararlar gerekir.", 23)
    card(s, "Tamamlanan", "Canlı veri hattı, dayanıklılık mekanizmaları, web arayüzü, Kubernetes/GitOps, metrikler, Spark/Iceberg ve statik Iceberg raporları.", 0.8, 1.45, 3.65, 2.0, GREEN)
    card(s, "Yerel kapsam", "Sistem Docker Desktop ve local Kubernetes eğitimine göre tasarlandı. Harita/OpenSky için internet gerekir.", 4.85, 1.45, 3.65, 2.0, BLUE)
    card(s, "Production öncesi", "TLS, kimlik doğrulama, yetkilendirme, uygun tile sağlayıcısı, kapasite planı, alarm politikası ve çok-worker WebSocket mimarisi ayrı ele alınmalı.", 8.9, 1.45, 3.65, 2.0, ORANGE)
    text(s, "Doğru yaklaşım: Eğitim ortamındaki varsayımları görünür kılmak; production gereksinimlerini gizlice varsaymamak.", 0.95, 4.45, 11.45, 0.5, 17, RED, True, PP_ALIGN.CENTER)
    bullets(s, ["Önce doğrulanmış, geri alınabilir ve gözlemlenebilir sistem.", "Sonra ölçülmüş ihtiyaçlara göre güvenlik ve ölçekleme yatırımı."], 2.55, 5.45, 8.2, 0.8, 18, NAVY)

    # 24 Project evolution
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "19. Projenin gelişim çizgisi", "Araçları tek seferde değil, her aşamada çalışan sistemi koruyarak ekledim.", 24)
    milestones = [
        ("01", "Temel altyapı", "Docker, Kafka, MongoDB", BLUE),
        ("02", "Canlı uygulama", "Producer, consumer, API, React", GREEN),
        ("03", "Dayanıklılık", "event_id, retry, DLQ, TTL", ORANGE),
        ("04", "Dağıtım", "Kubernetes, Argo CD, RC image'ları", PURPLE),
        ("05", "Gözlem + analiz", "Prometheus, Grafana, Spark, Iceberg", CYAN),
    ]
    for i, (num, h, b, col) in enumerate(milestones):
        x = 0.58 + i * 2.55
        rect(s, x, 2.0, 2.15, 2.1, LIGHT, True, "D9E2EC")
        rect(s, x + 0.72, 1.68, 0.7, 0.7, col, True)
        text(s, num, x + 0.72, 1.86, 0.7, 0.22, 12, WHITE, True, PP_ALIGN.CENTER)
        text(s, h, x + 0.16, 2.48, 1.83, 0.37, 13, NAVY, True, PP_ALIGN.CENTER)
        text(s, b, x + 0.16, 3.0, 1.83, 0.55, 10, GREY, False, PP_ALIGN.CENTER)
        if i < len(milestones) - 1:
            arrow(s, x + 2.15, 3.05, x + 2.55, 3.05, "8FA7BF")
    card(s, "Güncel referans", "v1.0.0-rc.5 yayımlandı; GitOps manifestleri multi-architecture image digest'lerine sabitlendi. Sonraki geliştirme, güncel Gold sorgularını kapsamlı statik HTML rapora dönüştürmek oldu.", 1.05, 5.25, 11.2, 1.05, GREEN)

    # 25 Kubernetes cluster
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "20. Kubernetes cluster: bu projede neyi ifade ediyor?", "Cluster, container'ları tek tek çalıştırmak yerine kaynak, ağ ve yaşam döngüsünü yöneten Kubernetes ortamıdır.", 25)
    rect(s, 0.7, 1.45, 11.95, 4.55, "EEF5FA", True, "9FB3C8")
    text(s, "Docker Desktop Kubernetes cluster", 1.0, 1.72, 4.7, 0.35, 20, NAVY, True)
    card(s, "Kubernetes API", "Manifestleri kabul eder; istenen durum ile gerçek durumu karşılaştıran control plane'in giriş noktasıdır.", 1.0, 2.35, 3.35, 1.35, BLUE)
    card(s, "Node / pod çalışma alanı", "Uygulama container'ları pod içinde çalışır. Deployment veya StatefulSet, pod'un nasıl yaşatılacağını tarif eder.", 4.95, 2.35, 3.35, 1.35, GREEN)
    card(s, "Cluster ağı + disk", "Service iç DNS sağlar; PVC kalıcı diski pod yaşam döngüsünden ayırır.", 8.9, 2.35, 2.85, 1.35, ORANGE)
    text(s, "Bu projede cluster içi uygulama namespace'i: flight-data-pipeline", 1.08, 4.35, 6.8, 0.32, 17, PURPLE, True)
    for i, (ns, col, note) in enumerate([
        ("flight-data-pipeline", BLUE, "uygulama"),
        ("argocd", PURPLE, "GitOps"),
        ("monitoring", GREEN, "Prometheus/Grafana"),
        ("reloader", ORANGE, "config restart"),
    ]):
        x = 1.0 + i * 2.85
        rect(s, x, 4.9, 2.35, 0.72, col, True)
        text(s, ns, x + 0.08, 5.04, 2.19, 0.22, 11, WHITE, True, PP_ALIGN.CENTER)
        text(s, note, x + 0.08, 5.33, 2.19, 0.16, 8, WHITE, False, PP_ALIGN.CENTER)

    # 26 Kubernetes full architecture
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "21. Cluster içindeki tam sistem mimarisi", "Tarayıcıdan kalıcı veriye kadar her bağlantı bir Kubernetes kaynağı üzerinden kurulur.", 26)
    text(s, "Tarayıcı", 0.2, 3.15, 0.72, 0.3, 13, NAVY, True, PP_ALIGN.CENTER)
    rect(s, 1.05, 1.25, 11.7, 4.9, "EEF5FA", True, "9FB3C8")
    text(s, "namespace: flight-data-pipeline", 1.35, 1.48, 4.1, 0.25, 13, PURPLE, True)
    node(s, "Ingress", 1.45, 2.55, 1.45, 0.82, ORANGE, "app.flight.test")
    node(s, "frontend\nService", 3.35, 2.55, 1.5, 0.82, BLUE, "ClusterIP")
    node(s, "frontend\nDeployment", 5.25, 2.55, 1.65, 0.82, BLUE, "Nginx + React")
    node(s, "backend\nService", 7.45, 2.55, 1.45, 0.82, PURPLE, "ClusterIP")
    node(s, "backend\nDeployment", 9.35, 2.55, 1.7, 0.82, PURPLE, "FastAPI + WS")
    node(s, "Kafka\nStatefulSet", 3.35, 4.4, 1.55, 0.82, ORANGE, "PVC + Service")
    node(s, "MongoDB\nStatefulSet", 6.05, 4.4, 1.65, 0.82, GREEN, "PVC + Service")
    node(s, "producer", 8.45, 4.4, 1.25, 0.82, BLUE, "Deployment")
    node(s, "consumer", 10.1, 4.4, 1.25, 0.82, GREEN, "Deployment")
    node(s, "topic-init", 1.45, 4.4, 1.25, 0.82, RED, "Job")
    arrow(s, 0.9, 3.0, 1.45, 3.0); arrow(s, 2.9, 2.96, 3.35, 2.96); arrow(s, 4.85, 2.96, 5.25, 2.96)
    arrow(s, 6.9, 2.96, 7.45, 2.96); arrow(s, 8.9, 2.96, 9.35, 2.96)
    arrow(s, 9.98, 3.37, 7.1, 4.4, PURPLE); arrow(s, 8.45, 4.8, 4.9, 4.8, BLUE); arrow(s, 10.1, 4.8, 4.9, 4.8, GREEN)
    arrow(s, 4.9, 4.8, 6.05, 4.8, GREEN); arrow(s, 2.7, 4.8, 3.35, 4.8, RED)
    text(s, "Ingress yalnız frontend'i dışarı açar. Kafka ve MongoDB sadece cluster içi DNS ile erişilir.", 1.2, 5.65, 11.1, 0.32, 15, RED, True, PP_ALIGN.CENTER)

    # 27 workload choices
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "22. Neden Deployment, StatefulSet ve Job farklı?", "Kubernetes'te kaynak tipi, servis davranışının bir parçasıdır.", 27)
    card(s, "Deployment — sürekli ve değiştirilebilir işçiler", "Producer, consumer, backend ve frontend. Pod çökerse yenisi açılır; image veya ayar değişince rolling update yapılır.", 0.75, 1.55, 3.65, 2.75, BLUE)
    card(s, "StatefulSet — sabit kimlik ve kalıcı veri", "Kafka-0 ve mongodb-0 için. Pod adı/DNS'i sabittir; PVC'leri korunduğu için yeniden başlatmada disk verisi kalır.", 4.84, 1.55, 3.65, 2.75, GREEN)
    card(s, "Job — bir kez tamamlanacak iş", "kafka-topic-init raw ve DLQ topic'lerini oluşturur/doğrular, sonra Complete olur. Bu yüzden Ready=0 normaldir.", 8.92, 1.55, 3.65, 2.75, ORANGE)
    text(s, "Kural: Sürekli hizmet = Deployment • Kimliği/verisi korunacak hizmet = StatefulSet • Sonlu başlangıç işi = Job", 0.8, 5.25, 11.7, 0.45, 18, NAVY, True, PP_ALIGN.CENTER)

    # 28 networking
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "23. Cluster ağı, Service ve DNS sözleşmesi", "Pod IP'leri geçicidir; uygulamalar pod adına değil Service adına bağlanır.", 28)
    node(s, "Tarayıcı", 0.5, 2.7, 1.35, 0.86, DARK, "app.flight.test")
    node(s, "Ingress", 2.4, 2.7, 1.35, 0.86, ORANGE, "nginx")
    node(s, "frontend:80", 4.3, 2.7, 1.55, 0.86, BLUE, "Service")
    node(s, "backend:8000", 6.5, 2.7, 1.65, 0.86, PURPLE, "Service")
    node(s, "kafka:29092", 8.85, 1.7, 1.7, 0.86, ORANGE, "Service")
    node(s, "mongodb:27017", 8.85, 3.85, 1.9, 0.86, GREEN, "Service")
    arrow(s, 1.85, 3.13, 2.4, 3.13); arrow(s, 3.75, 3.13, 4.3, 3.13); arrow(s, 5.85, 3.13, 6.5, 3.13)
    arrow(s, 8.15, 2.92, 8.85, 2.13, ORANGE); arrow(s, 8.15, 3.35, 8.85, 4.28, GREEN)
    card(s, "Normal Service", "backend, frontend, kafka ve mongodb için kısa, sabit erişim adı sağlar.", 1.0, 5.1, 4.6, 0.85, BLUE)
    card(s, "Headless Service", "Kafka/Mongo StatefulSet pod'larının sabit kimliği için: kafka-0.kafka-headless gibi DNS adları.", 6.8, 5.1, 4.9, 0.85, GREEN)
    text(s, "Frontend Nginx; /api, /health ve /ws isteklerini backend Service'ine proxy eder. Tarayıcı Kafka veya MongoDB'yi hiç görmez.", 0.75, 6.28, 11.8, 0.32, 15, NAVY, True, PP_ALIGN.CENTER)

    # 29 lifecycle and config
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "24. Pod yaşam döngüsü: başlatma, sağlık ve ayar", "Kubernetes sadece pod'u başlatmaz; hazır oluşunu ve yeniden başlama kararını da yönetir.", 29)
    card(s, "Init container", "Backend başlamadan önce MongoDB:27017 erişilebilir olana kadar bekler. Kafka volume init ise broker'ın data klasörünü non-root kullanıcı için hazırlar.", 0.75, 1.4, 3.75, 2.25, ORANGE)
    card(s, "Probe'lar", "startupProbe geç açılışı tolere eder; readinessProbe trafiğe hazır olmayı; livenessProbe kilitlenmiş süreçte yeniden başlatmayı belirler.", 4.8, 1.4, 3.75, 2.25, BLUE)
    card(s, "ConfigMap ve Secret", "Çalışma ayarları ConfigMap'te; OpenSky OAuth ve Grafana parolası Secret'ta. Secret Git'e veya ConfigMap'e yazılmaz.", 8.85, 1.4, 3.75, 2.25, GREEN)
    text(s, "ConfigMap değişince ortam değişkeni çalışan pod'a otomatik geçmez.", 0.95, 4.45, 11.4, 0.32, 18, NAVY, True, PP_ALIGN.CENTER)
    node(s, "Git'te\nbackend-config", 1.05, 5.25, 1.75, 0.8, BLUE)
    node(s, "Argo CD\nConfigMap apply", 3.55, 5.25, 1.75, 0.8, PURPLE)
    node(s, "Reloader\ndeğişimi görür", 6.05, 5.25, 1.75, 0.8, ORANGE)
    node(s, "Backend rolling\nrestart", 8.55, 5.25, 1.75, 0.8, GREEN)
    arrow(s, 2.8, 5.65, 3.55, 5.65); arrow(s, 5.3, 5.65, 6.05, 5.65); arrow(s, 7.8, 5.65, 8.55, 5.65)

    # 30 Argo CD
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "25. GitOps ve Argo CD: Git'teki istenen durum cluster'a nasıl gelir?", "GitOps'ta deploy komutu kişisel bilgisayarda değil; sürüm kontrollü manifest ve Argo CD Application tanımındadır.", 30)
    node(s, "GitHub main", 0.7, 2.75, 1.65, 0.9, DARK, "k8s/lesson-05")
    node(s, "Argo CD\nApplication", 3.35, 2.75, 1.85, 0.9, PURPLE, "source + destination")
    node(s, "Kustomize", 6.1, 2.75, 1.55, 0.9, BLUE, "manifest üretir")
    node(s, "Kubernetes API", 8.6, 2.75, 1.8, 0.9, GREEN, "apply")
    node(s, "Cluster\nkaynakları", 11.2, 2.75, 1.5, 0.9, ORANGE, "çalışan durum")
    arrow(s, 2.35, 3.2, 3.35, 3.2); arrow(s, 5.2, 3.2, 6.1, 3.2); arrow(s, 7.65, 3.2, 8.6, 3.2); arrow(s, 10.4, 3.2, 11.2, 3.2)
    card(s, "Uygulama Application'ı", "Kaynak: repository main / k8s/lesson-05. Hedef: cluster içindeki kubernetes.default.svc ve flight-data-pipeline namespace'i.", 0.85, 4.65, 5.5, 1.15, BLUE)
    card(s, "Bilinçli sync politikası", "Automated sync açık; fakat prune=false ve selfHeal=false. Yani Git'ten silinen kaynak otomatik silinmez, eldeki manuel fark da otomatik ezilmez.", 6.95, 4.65, 5.5, 1.15, ORANGE)

    # 31 CI/CD pipeline
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "26. CI/CD: kod değişikliğinden doğrulanmış image'a", "CI kalite kapısıdır; CD ise doğrulanmış çıktının sürümlenmesi ve dağıtıma hazırlanmasıdır.", 31)
    stages = [
        ("Pull request / main", "GitHub Actions tetiklenir", BLUE),
        ("Test", "Python, frontend, Playwright, Compose, integration", GREEN),
        ("Güvenlik", "pip-audit, npm audit, Trivy", RED),
        ("Multi-arch", "AMD64 + ARM64 image build", ORANGE),
        ("Release tag", "resmî Kafka/Mongo scan kapısı", PURPLE),
    ]
    for i, (h, b, col) in enumerate(stages):
        x = 0.5 + i * 2.56
        rect(s, x, 2.0, 2.05, 1.8, LIGHT, True, "D9E2EC")
        rect(s, x + 0.72, 1.72, 0.62, 0.62, col, True)
        text(s, str(i + 1), x + 0.72, 1.87, 0.62, 0.2, 12, WHITE, True, PP_ALIGN.CENTER)
        text(s, h, x + 0.14, 2.45, 1.77, 0.3, 12, NAVY, True, PP_ALIGN.CENTER)
        text(s, b, x + 0.12, 2.95, 1.81, 0.5, 9, GREY, False, PP_ALIGN.CENTER)
        if i < len(stages) - 1:
            arrow(s, x + 2.05, 2.95, x + 2.56, 2.95, "8FA7BF")
    card(s, "Neden release tag'de ek kapı var?", "Normal CI dört uygulama image'ını kontrol eder. Release workflow buna resmî Kafka ve MongoDB image'larının iki mimaride Trivy taramasını da ekler; kapı geçmeden publish başlamaz.", 1.0, 5.1, 11.25, 0.95, RED)

    # 32 release to GitOps
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "27. Release'ten GitOps deploy'a: izlenebilir teslim zinciri", "Image tag'i tek başına deploy değildir; dağıtım değişmez digest ve incelemeye açık Git değişikliğiyle yapılır.", 32)
    release_steps = [
        ("Tag", "v1.0.0-rc.5", PURPLE),
        ("GHCR", "AMD64/ARM64 image", BLUE),
        ("Kanıt", "SBOM + provenance + Cosign", GREEN),
        ("Offline", "checksum'lı paket", ORANGE),
        ("GitOps PR", "image digest'leri", RED),
        ("Argo sync", "cluster update", CYAN),
    ]
    for i, (h, b, col) in enumerate(release_steps):
        x = 0.35 + i * 2.12
        node(s, h, x, 2.25, 1.75, 0.8, col, b)
        if i < len(release_steps) - 1:
            arrow(s, x + 1.75, 2.65, x + 2.12, 2.65, "8FA7BF")
    card(s, "RC.5 uygulaması", "Yayımlanan RC.5 image digest'leri otomasyonun açtığı PR ile k8s/lesson-05 manifestlerine yazıldı. PR merge edilince Argo CD bu Git değişikliğini cluster'a sync eder.", 0.95, 4.55, 11.4, 1.15, GREEN)

    # 33 Prometheus details
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "28. Prometheus: metrikleri nasıl topluyor ve saklıyor?", "Prometheus pull modelini kullanır: uygulama metrik yayınlar, Prometheus belirli aralıkla gidip okur.", 33)
    node(s, "Producer /metrics", 0.65, 2.4, 1.9, 0.9, BLUE, "port 8000")
    node(s, "Backend /metrics", 0.65, 4.2, 1.9, 0.9, PURPLE, "Service http")
    node(s, "Service", 3.3, 3.3, 1.45, 0.9, GREEN, "label + port")
    node(s, "ServiceMonitor", 5.45, 3.3, 1.75, 0.9, ORANGE, "30 saniye")
    node(s, "Prometheus", 8.0, 3.3, 1.75, 0.9, RED, "time-series DB")
    node(s, "Grafana", 10.55, 3.3, 1.55, 0.9, CYAN, "PromQL sorgu")
    arrow(s, 2.55, 2.85, 3.3, 3.58); arrow(s, 2.55, 4.65, 3.3, 3.95); arrow(s, 4.75, 3.75, 5.45, 3.75); arrow(s, 7.2, 3.75, 8.0, 3.75); arrow(s, 9.75, 3.75, 10.55, 3.75)
    card(s, "Saklama ve altyapı", "kube-prometheus-stack; Prometheus için 2 gün retention ve 2 GiB PVC, Grafana için 1 GiB PVC. kube-state-metrics pod durumlarını, node exporter node kaynaklarını sağlar.", 0.85, 5.55, 5.55, 0.8, GREEN)
    card(s, "Metric tasarım kuralı", "icao24 ve event_id gibi sınırsız değerler label yapılmaz. Sadece sınırlı outcome/route gibi etiketler tutulur; zaman serisi patlaması önlenir.", 6.9, 5.55, 5.55, 0.8, RED)

    # 34 Observability architecture
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "29. Gözlemlenebilirlik: metrikler hangi yoldan akar?", "Log olayı anlatır; metrik ise zaman içindeki davranışı ölçer.", 34)
    node(s, "Producer\n:8000/metrics", 0.65, 2.2, 2.0, 1.0, BLUE, "OpenSky + Kafka")
    node(s, "Backend\n/metrics", 0.65, 4.1, 2.0, 1.0, PURPLE, "HTTP + WS + health")
    node(s, "Kubernetes\nService", 3.45, 3.15, 1.75, 1.0, GREEN, "sabit endpoint")
    node(s, "ServiceMonitor", 5.9, 3.15, 1.9, 1.0, ORANGE, "30 saniye")
    node(s, "Prometheus", 8.45, 3.15, 1.8, 1.0, RED, "toplar")
    node(s, "Grafana", 10.85, 3.15, 1.55, 1.0, CYAN, "gösterir")
    arrow(s, 2.65, 2.7, 3.45, 3.52); arrow(s, 2.65, 4.6, 3.45, 3.78)
    arrow(s, 5.2, 3.65, 5.9, 3.65); arrow(s, 7.8, 3.65, 8.45, 3.65); arrow(s, 10.25, 3.65, 10.85, 3.65)
    text(s, "Prometheus Operator + Prometheus + Grafana, Argo CD ile ayrı monitoring namespace'inde kurulur. Dashboard kaynak kod olarak Git'tedir.", 0.9, 5.75, 11.55, 0.48, 16, NAVY, True, PP_ALIGN.CENTER)

    # 26 Metrics detail
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "30. RC.5 ile genişletilen uygulama metrikleri", "Yeni metrikler, dış API ve Kafka teslim davranışını ölçülebilir hale getiriyor.", 35)
    card(s, "Producer / OpenSky", "• İstek sonucu: success, rate_limited, http_error, request_error, processing_error\n• İstek süresi histogramı\n• flight_producer_last_opensky_success_timestamp_seconds\n• Rate-limit nedeniyle toplam bekleme", 0.75, 1.4, 5.55, 3.45, BLUE)
    card(s, "Producer / Kafka", "• flight_producer_kafka_records_delivered_total\n• acks=all ve idempotent producer ayarı teslim güvenilirliğini destekler\n• Dashboard teslim hızını zaman içinde gösterir", 6.98, 1.4, 5.55, 3.45, GREEN)
    card(s, "Backend", "HTTP istek hızı / p95 süre, MongoDB-Kafka bağlantı durumu, işlenen ve atlanan mesaj, WebSocket batch/istemci sayısı ve flight_backend_data_freshness_seconds ölçülür.", 0.75, 5.25, 11.78, 1.0, PURPLE)

    # 27 Grafana
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "31. Grafana dashboard: operasyon sorularına cevap", "Dashboard yalnız 'çalışıyor mu?' değil, 'ne kadar sağlıklı çalışıyor?' sorusunu yanıtlar.", 36)
    cards = [
        ("Veri tazeliği", "Son MongoDB event'inin yaşı; stale/empty durumunu fark etmeye yardım eder.", BLUE),
        ("API performansı", "HTTP istek hızı ve p95 yanıt süresi ile kullanıcıya yansıyan gecikme.", PURPLE),
        ("Kafka akışı", "Backend'in işleme hızı; producer'ın OpenSky sonucu ve Kafka teslim hızı.", ORANGE),
        ("Kubernetes sağlığı", "Pod Ready, CPU, bellek, RX/TX ağ trafiği, node kaynakları ve restartlar.", GREEN),
    ]
    for i, (h, b, col) in enumerate(cards):
        x, y = 0.75 + (i % 2) * 6.1, 1.45 + (i // 2) * 1.75
        card(s, h, b, x, y, 5.6, 1.3, col)
    text(s, "Önemli yorum: topic-init bir Job olduğu için tamamlandıktan sonra Ready=0 görünmesi hata değildir; dashboard bu pod'u sağlık panelinden hariç tutar.", 0.9, 5.55, 11.45, 0.46, 15, RED, True, PP_ALIGN.CENTER)

    # 28 Configuration and security
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "32. Güvenlik ve yapılandırma disiplini", "Yerel eğitim kapsamı olsa da secret, image ve bağımlılık yönetimini bilinçli tuttum.", 37)
    card(s, "Secret yönetimi", "OpenSky OAuth client bilgileri yalnız local .env veya Kubernetes Secret'ta bulunur. Git, ConfigMap, terminal çıktısı ve loglara yazılmaz.", 0.8, 1.45, 3.7, 2.25, RED)
    card(s, "İç ağ sınırı", "Release Compose host'a yalnız 127.0.0.1:5175 frontend portunu açar. Backend, Kafka ve MongoDB doğrudan host ağına açılmaz.", 4.82, 1.45, 3.7, 2.25, BLUE)
    card(s, "Tedarik zinciri", "Hash doğrulamalı lock dosyaları; CI'da pip-audit, npm audit, AMD64/ARM64 Trivy taraması; SBOM, provenance ve keyless Cosign imzası.", 8.85, 1.45, 3.7, 2.25, GREEN)
    card(s, "Kasıtlı kapsam sınırı", "Plaintext Kafka ve kimlik doğrulamasız MongoDB sadece localhost eğitimi içindir. Public production için TLS, auth, authorization ve ağ politikaları gerekir.", 2.8, 4.45, 7.75, 1.35, ORANGE)

    # 29 Incremental analytical refresh
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "33. Iceberg dashboard yenileme: güvenli batch orkestrasyonu", "Yeni analitik aşama, canlı yolu etkilemeden kontrollü ve artımlı çalışır.", 38)
    sequence = [
        ("1", "Bronze watermark", "MAX(ingested_at) okunur", BLUE),
        ("2", "5 dk overlap", "Zaman sınırı riski azaltılır", CYAN),
        ("3", "Mongo export", "Salt-okunur JSONL.gz", GREEN),
        ("4", "Bronze anti-join", "Yeni event_id ölçülür / eklenir", ORANGE),
        ("5", "Silver + Gold", "Kalite ve özetler güncellenir", PURPLE),
        ("6", "HTML rapor", "Yeni zaman damgalı dosya", RED),
    ]
    for i, (n, h, b, col) in enumerate(sequence):
        x = 0.48 + i * 2.12
        rect(s, x, 2.0, 1.78, 2.1, LIGHT, True, "D9E2EC")
        rect(s, x + 0.59, 1.72, 0.6, 0.6, col, True)
        text(s, n, x + 0.59, 1.85, 0.6, 0.22, 12, WHITE, True, PP_ALIGN.CENTER)
        text(s, h, x + 0.1, 2.42, 1.57, 0.35, 12, NAVY, True, PP_ALIGN.CENTER)
        text(s, b, x + 0.12, 2.98, 1.52, 0.55, 9, GREY, False, PP_ALIGN.CENTER)
        if i < len(sequence) - 1:
            arrow(s, x + 1.78, 3.03, x + 2.12, 3.03, "8FA7BF")
    card(s, "Önce prova, sonra yazma", "--dry-run yalnız export ve anti-join sonucunu gösterir. --apply bir adım hata verirse set -e ile sonraki adıma geçmez; rapor yalnız güncel Iceberg tablolarından üretilir.", 1.1, 5.25, 11.1, 0.92, GREEN)

    # 30 Iceberg guarantees
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "34. Iceberg'de doğruluk ve geri kazanım", "Her tablo yazımı güçlüdür; çok tablo akışında ise bilinçli toparlanma stratejisi kullanılır.", 39)
    card(s, "Tek tablo atomic snapshot", "Bronze append veya Gold overwrite başarılı commit olmadıkça yeni tablo görünmez; önceki Iceberg snapshot korunur.", 0.75, 1.55, 5.45, 1.55, GREEN)
    card(s, "Çok tablo sınırı", "Silver ve Rejected; ayrıca Gold tabloları tek bir ortak transaction değildir. Birinin commit'i başarılı, diğerinin başarısız kalabilir.", 6.9, 1.55, 5.45, 1.55, ORANGE)
    card(s, "Toparlanma", "Her aşamada event_id anti-join kullanıldığı için akış yeniden çalıştırılabilir. Başarılı yazılanlar atlanır; eksik sınıflandırma / özet tamamlanır.", 0.75, 3.8, 5.45, 1.55, BLUE)
    card(s, "Time-travel", "Iceberg metadata tablosundaki snapshot_id ile VERSION AS OF sorgusu yapılır. Bu, dosya klasörlerini elle saymaktan daha güvenilir bir sürümleme modelidir.", 6.9, 3.8, 5.45, 1.55, PURPLE)
    text(s, "Bu yaklaşım canlı sistemdeki idempotency fikrini analitik batch katmanına da taşır.", 1.0, 6.25, 11.2, 0.35, 17, NAVY, True, PP_ALIGN.CENTER)

    # 31 Gold model
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "35. Gold tabloları: karar verilebilir analitik veriler", "Gold, satır seviyesindeki olayları tekrar kopyalamaz; güncel Silver/Rejected veriden özet üretir.", 40)
    card(s, "gold_hourly_traffic", "Saat + kaynak ülke bazında: konum olayı, benzersiz uçak, havadaki olay, ortalama barometrik irtifa ve ortalama hız.", 0.75, 1.4, 3.65, 2.2, GREEN)
    card(s, "gold_hourly_activity", "Saat bazında toplam aktivite: konum olayı, benzersiz uçak, havada olma oranı, ortalama irtifa ve hız.", 4.84, 1.4, 3.65, 2.2, BLUE)
    card(s, "gold_data_quality", "Silver kabul ve rejected kayıtlarının kalite durumu / nedeni / olay sayısı özeti.", 8.92, 1.4, 3.65, 2.2, PURPLE)
    text(s, "Gold tam yenilemesi, bu tabloları güncel Silver ve Rejected verisinden hesaplayarak kendi yeni Iceberg snapshot'larını oluşturur.", 0.95, 4.55, 11.45, 0.5, 17, NAVY, True, PP_ALIGN.CENTER)
    bullets(s, ["Bronze: kaynak olaylar", "Silver: kalite kuralını geçen olaylar", "Rejected: nedenleriyle ayrı tutulan olaylar", "Gold: rapor ve dashboard için özet"], 2.65, 5.55, 8.2, 0.85, 15)

    # 32 HTML report
    s = P.slides.add_slide(P.slide_layouts[6]); title(s, "36. Güncel HTML Iceberg raporu", "Iceberg katmanlarından üretilen, tarayıcıda doğrudan açılan tek dosyalık yönetim özeti.", 41)
    card(s, "Özet kartları", "Bronze / Silver / Rejected event sayıları, Silver kabul oranı, en yoğun saat, o saatteki uçak sayısı ve havada olma oranı.", 0.75, 1.35, 3.65, 2.0, CYAN)
    card(s, "Zaman serileri", "Saatlik Silver konum olayı, benzersiz uçak ve havada olma oranı için bağımsız SVG çizgi grafikleri.", 4.84, 1.35, 3.65, 2.0, BLUE)
    card(s, "Yoğunluk + kalite", "En yoğun 10 kaynak ülke yatay grafikle; Silver veri kalitesi de durum / neden / event sayısı tablosuyla gösterilir.", 8.92, 1.35, 3.65, 2.0, PURPLE)
    card(s, "Neden bu tasarım?", "Rapor Bronze/Silver/Rejected sayıları ve Gold özetlerini Iceberg'den okur. Hiçbir veri katmanına yazmaz; CDN veya ek servis gerekmez. Her --apply yeni zaman damgalı dosya üretir.", 1.3, 4.5, 10.75, 1.35, GREEN)
    text(s, "Bu, ham streaming olaylarını teknik olmayan bir yönetici için okunabilir analitik çıktıya dönüştüren son katmandır.", 0.95, 6.3, 11.45, 0.35, 16, NAVY, True, PP_ALIGN.CENTER)

    # 33 close
    s = P.slides.add_slide(P.slide_layouts[6])
    rect(s, 0, 0, 13.333, 7.5, NAVY)
    rect(s, 0, 0, 13.333, 0.18, CYAN)
    text(s, "Sonuç", 0.78, 1.1, 3.0, 0.6, 30, WHITE, True)
    text(s, "Canlı uçuş verisini yalnızca haritada göstermedik;\nverinin güvenilir, izlenebilir ve analiz edilebilir bir yaşam döngüsünü kurduk.", 0.8, 2.0, 11.4, 1.1, 24, "D9EAF7", True)
    for i, (h, b, col) in enumerate([
        ("Canlı sistem", "OpenSky → Kafka → MongoDB → FastAPI → React", CYAN),
        ("Dayanıklılık", "Retry, DLQ, idempotent upsert, backup/restore", ORANGE),
        ("Analitik", "Spark, Gold HTML raporu, Iceberg snapshot", PURPLE),
    ]):
        x = 0.85 + i * 4.1
        rect(s, x, 4.4, 3.5, 1.15, "1F4A6D", True, "2E648E")
        text(s, h, x + 0.2, 4.62, 3.1, 0.25, 15, col, True, PP_ALIGN.CENTER)
        text(s, b, x + 0.18, 4.97, 3.15, 0.28, 10, WHITE, False, PP_ALIGN.CENTER)
    text(s, "Güncel referans: v1.0.0-rc.5 • Teşekkürler • Sorularınız?", 0.8, 6.45, 11.7, 0.35, 18, WHITE, True, PP_ALIGN.CENTER)


add_content()
OUT.parent.mkdir(parents=True, exist_ok=True)
P.save(OUT)
print(f"Oluşturuldu: {OUT} ({len(P.slides)} slayt)")
