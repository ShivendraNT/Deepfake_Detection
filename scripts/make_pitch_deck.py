"""Generate Satyapan Hackathon Pitch Deck (14 Slides, 16:9 widescreen)."""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# --- Color Palette ---
BG_DARK = RGBColor(15, 23, 42)        # Slate 900
BG_LIGHT = RGBColor(248, 250, 252)    # Slate 50
CARD_BG = RGBColor(255, 255, 255)     # White
CARD_BORDER = RGBColor(203, 213, 225) # Slate 300
PRIMARY = RGBColor(29, 78, 216)       # Blue 700
ACCENT_GREEN = RGBColor(16, 185, 129) # Emerald 500
ACCENT_RED = RGBColor(220, 38, 38)    # Red 600
ACCENT_AMBER = RGBColor(217, 119, 6)  # Amber 600
TEXT_MAIN = RGBColor(15, 23, 42)      # Slate 900
TEXT_MUTED = RGBColor(71, 85, 105)    # Slate 600
TEXT_WHITE = RGBColor(255, 255, 255)  # White
TEXT_CYAN = RGBColor(56, 189, 248)    # Sky 400


def create_deck(output_path: Path) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_header(slide, title_text, category="SATYAPAN · RAKSHAM HACKATHON"):
        # Top banner category
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_c = cat_box.text_frame
        tf_c.word_wrap = True
        p_c = tf_c.paragraphs[0]
        p_c.text = category.upper()
        p_c.font.size = Pt(11)
        p_c.font.bold = True
        p_c.font.color.rgb = PRIMARY

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.8))
        tf_t = title_box.text_frame
        tf_t.word_wrap = True
        p_t = tf_t.paragraphs[0]
        p_t.text = title_text
        p_t.font.size = Pt(26)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_MAIN

    def set_slide_bg(slide, color):
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=CARD_BORDER):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = bg_color
        if border_color:
            shape.line.color.rgb = border_color
            shape.line.width = Pt(1.5)
        else:
            shape.line.fill.background()
        return shape

    # ==========================================
    # SLIDE 1: TITLE SLIDE (Dark Theme)
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s1, BG_DARK)

    # Accent badge
    badge = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.2), Inches(4.2), Inches(0.45))
    badge.fill.solid()
    badge.fill.fore_color.rgb = RGBColor(30, 41, 59)
    badge.line.color.rgb = PRIMARY
    b_tf = badge.text_frame
    b_p = b_tf.paragraphs[0]
    b_p.text = "🛡️ DTU · RAKSHAM HACKATHON 2026"
    b_p.font.size = Pt(12)
    b_p.font.bold = True
    b_p.font.color.rgb = TEXT_CYAN
    b_p.alignment = PP_ALIGN.CENTER

    # Big Title
    t_box = s1.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.5), Inches(2.2))
    tf = t_box.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = "SATYAPAN (सत्यापन)"
    p1.font.size = Pt(50)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE

    p2 = tf.add_paragraph()
    p2.text = "Transaction-Anchored Deepfake & Financial Fraud Defense for Indian Enterprises"
    p2.font.size = Pt(22)
    p2.font.color.rgb = RGBColor(203, 213, 225)

    # Subtitle / Core Idea Card
    add_card(s1, Inches(0.8), Inches(4.2), Inches(11.7), Inches(1.3), bg_color=RGBColor(30, 41, 59), border_color=PRIMARY)
    c_box = s1.shapes.add_textbox(Inches(1.0), Inches(4.3), Inches(11.3), Inches(1.1))
    c_tf = c_box.text_frame
    c_tf.word_wrap = True
    cp1 = c_tf.paragraphs[0]
    cp1.text = "Core Thesis: Detectors can be deceived; payment invariants cannot."
    cp1.font.size = Pt(16)
    cp1.font.bold = True
    cp1.font.color.rgb = ACCENT_GREEN
    cp2 = c_tf.add_paragraph()
    cp2.text = "We anchor verification directly to the pending payment. Communications evidence can only raise security scrutiny, never lower it."
    cp2.font.size = Pt(13)
    cp2.font.color.rgb = RGBColor(226, 232, 240)

    # Team Box
    team_box = s1.shapes.add_textbox(Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.0))
    t_tf = team_box.text_frame
    tp = t_tf.paragraphs[0]
    tp.text = "Team Members: Shivendra (Lead/Arch) · Kartikey (Checkers & Research) · Saarika (Acoustics) · Saksham (UI/Workflows)"
    tp.font.size = Pt(13)
    tp.font.bold = True
    tp.font.color.rgb = TEXT_CYAN

    s1.notes_slide.notes_text_frame.text = "Good morning judges. We are Team Satyapan from DTU. We are presenting an end-to-end defense system built for Indian companies to stop multi-crore deepfake voice and invoice scams before funds leave the bank."

    # ==========================================
    # SLIDE 2: THE PROBLEM STATEMENT
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s2, BG_LIGHT)
    add_header(s2, "Why This Problem? The Real-World Attack Crisis")

    # 3 Column Cards
    col_w = Inches(3.7)
    gap = Inches(0.3)
    top_pos = Inches(1.8)
    card_h = Inches(4.8)

    # Card 1: The Arup Precedent
    add_card(s2, Inches(0.8), top_pos, col_w, card_h)
    box1 = s2.shapes.add_textbox(Inches(1.0), top_pos + Inches(0.2), col_w - Inches(0.4), card_h - Inches(0.4))
    tf1 = box1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🚨 The Global Precedent\n₹200+ Crore Arup Scam"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    bullets1 = [
        "In 2024, a finance executive in Hong Kong paid HK$200M (~₹200 Cr) after a video call with a deepfake CFO and cloned colleagues.",
        "Attackers did NOT need flawless video: they used social engineering, urgency, and familiar faces to force compliance.",
        "Traditional IT security (antivirus, firewalls) was completely blind to this attack vector."
    ]
    for b in bullets1:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MAIN

    # Card 2: Indian SME Landscape
    add_card(s2, Inches(0.8) + col_w + gap, top_pos, col_w, card_h)
    box2 = s2.shapes.add_textbox(Inches(1.0) + col_w + gap, top_pos + Inches(0.2), col_w - Inches(0.4), card_h - Inches(0.4))
    tf2 = box2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "🇮🇳 The Indian SME Reality\nUnprotected AP Teams"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    bullets2 = [
        "Over 1.1 million financial cyber frauds reported annually on the national 1930 portal.",
        "Indian SME Accounts Payable (AP) clerks transfer ₹10L - ₹1Cr daily via RTGS/NEFT.",
        "When an executive receives an urgent WhatsApp voice note sounding like the CEO, they execute it under pressure.",
        "Vendors frequently change banks during routine business, creating the perfect camouflage for hackers."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MAIN

    # Card 3: The Multi-Vector Trap
    add_card(s2, Inches(0.8) + (col_w + gap) * 2, top_pos, col_w, card_h)
    box3 = s2.shapes.add_textbox(Inches(1.0) + (col_w + gap) * 2, top_pos + Inches(0.2), col_w - Inches(0.4), card_h - Inches(0.4))
    tf3 = box3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "🕸️ The Multi-Vector Trap\nSiloed Tools Fail"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = ACCENT_AMBER
    bullets3 = [
        "Modern fraud is NEVER a single call: it is an orchestrated composite attack.",
        "Vector 1: Look-alike domain email with altered bank account.",
        "Vector 2: Forged PDF invoice with matching new IFSC.",
        "Vector 3: Urgent AI-cloned voice call on Meet or WhatsApp.",
        "Checking email alone or audio alone misses the full picture."
    ]
    for b in bullets3:
        p = tf3.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MAIN

    s2.notes_slide.notes_text_frame.text = "Why was this problem statement created? Because modern corporate scams are multi-vector. The Arup ₹200 Crore incident proved that attackers combine cloned audio, fake invoices, and spoofed emails. Indian SMEs have zero automated verification before money is released."

    # ==========================================
    # SLIDE 3: WHY EXISTING AI DETECTORS FAIL
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s3, BG_LIGHT)
    add_header(s3, "The Blind Spot: Why Pure AI Detectors Fail in Real Life")

    add_card(s3, Inches(0.8), Inches(1.8), Inches(11.7), Inches(2.2), bg_color=CARD_BG)
    t_box = s3.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(11.3), Inches(2.0))
    tf = t_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "⚠️ Research Reality Check: The 'False Safety' Danger"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    pts = [
        "Academic & In-The-Wild Fragility (Deepfake-Eval-2024): Open-source deepfake detectors lose ~50% AUC when exposed to real-world compression, background noise, and codec artifacts.",
        "Commercial Voice Realism (DF26): Modern voice generators deceive human listeners 47.4% of the time. The best detector achieves only 34.5% AUROC against commercial tools.",
        "The Dangerous Trap: If an AI detector tells a clerk 'This voice is 85% Likely Real', the clerk lets their guard down and releases the payment to the criminal!"
    ]
    for pt in pts:
        p = tf.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_MAIN

    # Bottom comparison cards
    add_card(s3, Inches(0.8), Inches(4.3), Inches(5.7), Inches(2.3), bg_color=RGBColor(254, 242, 242), border_color=ACCENT_RED)
    b1 = s3.shapes.add_textbox(Inches(1.0), Inches(4.4), Inches(5.3), Inches(2.1))
    tf_b1 = b1.text_frame
    tf_b1.word_wrap = True
    p = tf_b1.paragraphs[0]
    p.text = "❌ Flawed Approach: Standalone Deepfake Detector"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    b_pts = [
        "Relies purely on acoustic or video classifiers.",
        "Can be fooled by prompt injection and audio filters.",
        "Treats high confidence as 'safe to pay'."
    ]
    for b in b_pts:
        p = tf_b1.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)

    add_card(s3, Inches(6.8), Inches(4.3), Inches(5.7), Inches(2.3), bg_color=RGBColor(240, 253, 244), border_color=ACCENT_GREEN)
    b2 = s3.shapes.add_textbox(Inches(7.0), Inches(4.4), Inches(5.3), Inches(2.1))
    tf_b2 = b2.text_frame
    tf_b2.word_wrap = True
    p = tf_b2.paragraphs[0]
    p.text = "✅ Satyapan Approach: Transaction-Anchored Policy"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    g_pts = [
        "Anchored to the financial transaction & vendor ledger.",
        "AI scores can only RAISE scrutiny, NEVER lower it.",
        "Detectors decide WHO verifies, not whether to pay."
    ]
    for g in g_pts:
        p = tf_b2.add_paragraph()
        p.text = "• " + g
        p.font.size = Pt(12)

    s3.notes_slide.notes_text_frame.text = "Most teams build a simple deepfake classifier. But research proves that real-world codecs degrade accuracy by 50%. Relying solely on an AI score creates a dangerous false sense of safety. Satyapan ensures AI scores never decide whether money is paid."

    # ==========================================
    # SLIDE 4: OUR CORE INNOVATION: RAISE-ONLY PRINCIPLE
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s4, BG_LIGHT)
    add_header(s4, "Our Innovation: The 'Raise-Only' Policy Principle")

    # Step cards: Floor -> Detectors -> Escalation
    w_card = Inches(11.7)
    add_card(s4, Inches(0.8), Inches(1.8), w_card, Inches(1.5), bg_color=CARD_BG)
    bx = s4.shapes.add_textbox(Inches(1.0), Inches(1.9), w_card - Inches(0.4), Inches(1.3))
    tfx = bx.text_frame
    tfx.word_wrap = True
    p = tfx.paragraphs[0]
    p.text = "1. Deterministic Security Floor (Internal Ledger First)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    p = tfx.add_paragraph()
    p.text = "Routine recurring payments to established vendor accounts start at PASS. But ANY vendor bank account, IFSC, or payment method change automatically forces a mandatory baseline floor of VERIFY — regardless of how genuine the caller sounds."
    p.font.size = Pt(13)

    add_card(s4, Inches(0.8), Inches(3.5), w_card, Inches(1.5), bg_color=CARD_BG)
    bx2 = s4.shapes.add_textbox(Inches(1.0), Inches(3.6), w_card - Inches(0.4), Inches(1.3))
    tf2 = bx2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "2. The 'Raise-Only' Invariant (No AI Downgrades Allowed)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_AMBER
    p = tf2.add_paragraph()
    p.text = "Communications evidence (email headers, invoice PDFs, acoustic voice scores) can only ESCALATE risk bands (PASS -> VERIFY -> HOLD). A 'clean' score from an AI model can NEVER lower a security floor. Attackers cannot use polite speech or high-end voice clones to bypass security."
    p.font.size = Pt(13)

    add_card(s4, Inches(0.8), Inches(5.2), w_card, Inches(1.5), bg_color=CARD_BG)
    bx3 = s4.shapes.add_textbox(Inches(1.0), Inches(5.3), w_card - Inches(0.4), Inches(1.3))
    tf3 = bx3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "3. Multi-Signal Escalation (Lattice Fusion)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    p = tf3.add_paragraph()
    p.text = "When multiple independent detectors flag anomalies (e.g. Synthetic Voice score >= threshold + Look-alike domain detected) -> the system triggers an immediate hard HOLD, freezing the payment button and requiring Out-of-Band executive clearance."
    p.font.size = Pt(13)

    s4.notes_slide.notes_text_frame.text = "Here is our core innovation: The Raise-Only Principle. We start with trusted internal company data. If a bank account changes, verification is required by default. External media can only escalate scrutiny, never lower it."

    # ==========================================
    # SLIDE 5: HIGH-LEVEL ARCHITECTURE (5 LAYERS)
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s5, BG_LIGHT)
    add_header(s5, "System Architecture: The 5 Defense Layers")

    layers = [
        ("Layer 1: Intake & Custody Vault", "SHA-256 fingerprinting before parsing · Tamper-evident hash chain · S3 Object Lock anchor", PRIMARY),
        ("Layer 2: Multi-Signal Detectors", "Parallel email parser, domain typo-squatting, PDF invoice regex, ONNX acoustic voice AI, Whisper ASR", PRIMARY),
        ("Layer 3: Policy Engine Brain", "Deterministic floor table · Raise-only escalation lattice · Mathematical rule execution (Zero LLM hallucinations)", ACCENT_AMBER),
        ("Layer 4: Real-Time Applications", "Accounts Payable Console (React) · Google Meet Extension (WebAssembly) · Out-of-Band (OOB) CFO Confirm", ACCENT_GREEN),
        ("Layer 5: Golden-Hour Incident Pack", "1-click generation of 1930 Cyber Police calling script (UTR on Line 1) · Bank freeze notice · NCRP complaint draft", ACCENT_RED),
    ]

    for i, (title, desc, col) in enumerate(layers):
        y_pos = Inches(1.8) + Inches(i * 1.05)
        add_card(s5, Inches(0.8), y_pos, Inches(11.7), Inches(0.95), bg_color=CARD_BG, border_color=col)
        # indicator bar
        bar = s5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), y_pos, Inches(0.2), Inches(0.95))
        bar.fill.solid()
        bar.fill.fore_color.rgb = col
        bar.line.fill.background()

        tb = s5.shapes.add_textbox(Inches(1.2), y_pos + Inches(0.08), Inches(11.1), Inches(0.8))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = col
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MAIN

    s5.notes_slide.notes_text_frame.text = "This slide shows our 5 defense layers. Layer 1 hashes everything for legal custody. Layer 2 runs multi-signal detectors in parallel. Layer 3 evaluates rules via the Policy Engine. Layer 4 delivers the user experience on Meet and desktop. Layer 5 provides instant incident recovery."

    # ==========================================
    # SLIDE 6: LAYER 1 & 2 - DETECTORS MESH
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s6, BG_LIGHT)
    add_header(s6, "Layers 1 & 2: Ingestion & Multi-Signal Detectors")

    det_cards = [
        ("✉️ Email & Domain Checker (T03, T04)", [
            "Parses raw .eml RFC 822 messages and MTA headers.",
            "Enforces SPF, DKIM, and DMARC authentication.",
            "Levenshtein distance & Unicode confusables catch look-alike domains (e.g. acme-supp1ies.example).",
            "Enforces RBI mandate: claims of Indian banks must reside on legitimate .bank.in domains."
        ]),
        ("📄 Invoice PDF Inspector (T08)", [
            "Extracts text, tables, and metadata via pdfplumber.",
            "Regex extraction for 11-digit IFSC, Account Number, GSTIN, UPI IDs, and net amounts.",
            "Master Diff: compares extracted bank details against company's approved vendor ledger.",
            "Detects PDF editing metadata (Acrobat modification artifacts)."
        ]),
        ("🎙️ Voice AI Acoustic Model (T07, T17)", [
            "Acoustic feature extractor running on 5-second PCM windows at 16kHz.",
            "ONNX XLS-R acoustic neural network running on CPU / WebAssembly.",
            "Detects phase and spectral anomalies typical of commercial TTS/voice-cloning engines.",
            "Transcribes speech to text via Whisper in <3.2s latency."
        ]),
        ("⚡ Attacker-Invariant Asks (T05)", [
            "Deterministic regex engine scanning for fraud intent (Asks A1 - A7).",
            "Catches urgency, secret escrow requests, credential/OTP demands, and remote desktop installs (AnyDesk).",
            "Zero LLM latency; operates in English, Devanagari Hindi, and romanised Hinglish."
        ]),
    ]

    col_w2 = Inches(5.7)
    gap2 = Inches(0.3)
    row_h2 = Inches(2.4)

    for i, (title, b_list) in enumerate(det_cards):
        col = i % 2
        row = i // 2
        x = Inches(0.8) + col * (col_w2 + gap2)
        y = Inches(1.8) + row * (row_h2 + gap2)

        add_card(s6, x, y, col_w2, row_h2)
        tb = s6.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), col_w2 - Inches(0.4), row_h2 - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = PRIMARY
        for b in b_list:
            p = tf.add_paragraph()
            p.text = "• " + b
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_MAIN

    s6.notes_slide.notes_text_frame.text = "Here is what happens in Layers 1 and 2. We inspect every channel in parallel. Our email module verifies headers and catches lookalike domains. Our invoice parser extracts bank accounts to catch account-swaps. Our voice AI scores synthetic frequencies, and our ask extractor catches fraud intent without latency."

    # ==========================================
    # SLIDE 7: LAYER 3 - THE POLICY ENGINE BRAIN
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s7, BG_LIGHT)
    add_header(s7, "Layer 3: The Deterministic Policy Engine")

    # Table of Bands
    add_card(s7, Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.0))
    tb = s7.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(11.3), Inches(4.8))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Three Deterministic Risk Bands (Governed by Code, Not AI)"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = TEXT_MAIN

    sections = [
        ("🟢 PASS Band (Routine Execution)", "Established vendor, historical payment amounts, unchanged bank details, and all detectors clean. Maker proceeds with standard workflow.", ACCENT_GREEN),
        ("🟡 VERIFY Band (Scrutiny Required)", "Vendor bank account differs from master ledger, dormant account reactivated, or weak signal flags. Mandatory callback on on-file registered phone number OR Out-of-Band CFO approval required before release.", ACCENT_AMBER),
        ("🔴 HOLD Band (Transaction Frozen)", "Synthetic voice detected (>= 2 consecutive windows), look-alike domain from unauthenticated sender, or OTP/AnyDesk ask. Payment execution button strictly disabled; security notified.", ACCENT_RED),
    ]

    for title, desc, col in sections:
        p = tf.add_paragraph()
        p.text = "\n" + title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = col
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MAIN

    p = tf.add_paragraph()
    p.text = "\n🛡️ Prompt-Injection Immunity:"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    p = tf.add_paragraph()
    p.text = "LLMs are restricted to text summarization only and have ZERO write access to security bands. 30/30 red-team prompt injections failed to bypass this engine."
    p.font.size = Pt(11)

    s7.notes_slide.notes_text_frame.text = "Layer 3 is the mathematical brain. There are three bands: PASS, VERIFY, and HOLD. Any bank change forces at least VERIFY. Strong anomalies force HOLD. Generative LLMs have zero ability to alter these bands, making the engine completely prompt-injection proof."

    # ==========================================
    # SLIDE 8: LAYER 4 - TWO USER APPLICATIONS
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s8, BG_LIGHT)
    add_header(s8, "Layer 4: Real-Time Enterprise Applications")

    # Card 1: Meet Extension
    add_card(s8, Inches(0.8), Inches(1.8), Inches(5.7), Inches(5.0))
    tb1 = s8.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🎥 Google Meet Chrome Extension\n(Live Video & Audio Calls)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    pts1 = [
        "Runs on the presenter's browser during live Meet / Teams calls.",
        "Captures remote party's audio stream via chrome.tabCapture API.",
        "On-Device AI Inference: Runs ONNX neural network in WebAssembly (zero cloud audio latency).",
        "Floating Side Panel UI: Displays real-time synthetic voice meter (e.g. 🚨 Likely Synthetic Voice: 94%).",
        "Live Intent Chips: Highlights risky requests on screen in real time: [New Account], [Secrecy], [Bypass Approval]."
    ]
    for pt in pts1:
        p = tf1.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)

    # Card 2: AP Desk Console
    add_card(s8, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0))
    tb2 = s8.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "🖥️ Payment Verification Desk\n(React + Vite Console)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    pts2 = [
        "Dedicated web console for Accounts Payable (Maker / Checker) teams.",
        "Transaction Card: Highlights old vs new bank details, IFSC, and amounts.",
        "Out-of-Band (OOB) CFO Confirm: One-tap button sends instant push/email to real CFO: 'Did you approve this payment?'",
        "Bilingual Explanations: Displays clear Hindi (Devanagari) & English reasons for why payment is held.",
        "Evidence Dossier: Displays verified SHA-256 fingerprints before anyone opens suspicious files."
    ]
    for pt in pts2:
        p = tf2.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)

    s8.notes_slide.notes_text_frame.text = "Layer 4 delivers our two client applications. Our Chrome extension protects live video meetings with on-device AI and alert chips. Our React web desk gives finance clerks an interactive cockpit with transaction comparison and one-tap Out-of-Band CFO approval."

    # ==========================================
    # SLIDE 9: LAYER 5 - GOLDEN HOUR RECOVERY PACK
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s9, BG_LIGHT)
    add_header(s9, "Layer 5: The 'Golden Hour' Incident Response Pack (T16)")

    add_card(s9, Inches(0.8), Inches(1.8), Inches(11.7), Inches(1.4), bg_color=CARD_BG)
    tb = s9.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(11.3), Inches(1.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "⏱️ The 60-Minute Recovery Window"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    p = tf.add_paragraph()
    p.text = "If funds are accidentally transferred, the first 60 minutes ('Golden Hour') are the only window to freeze mule accounts before criminals cash out. Satyapan automates the entire legal and banking emergency response in one click."
    p.font.size = Pt(12)

    # 3 Artifact cards
    w_pack = Inches(3.7)
    gap_p = Inches(0.3)
    top_p = Inches(3.4)
    h_p = Inches(3.4)

    pack_items = [
        ("📞 1930 Helpline Call Script", [
            "UTR Number on Line 1: Gives the operator the critical transaction ID immediately.",
            "Pre-filled beneficiary account, IFSC, amount (formatted in ₹ Lakhs), and timestamps.",
            "Step-by-step phone dialogue so panicking clerks don't stutter or miss vital facts."
        ], PRIMARY),
        ("🏦 Bank Nodal Freeze Email", [
            "Formal legal request addressed to beneficiary bank's Nodal Fraud Desk.",
            "Formats transaction hashes and evidence references.",
            "Demands immediate lien/freeze on the recipient mule account under RBI guidelines."
        ], ACCENT_AMBER),
        ("🏛️ NCRP Cyber Portal Draft", [
            "Pre-filled incident complaint formatted for cybercrime.gov.in.",
            "Includes cryptographic SHA-256 evidence chain.",
            "Human-in-the-Loop: Prepared instantly, reviewed and submitted by the human officer."
        ], ACCENT_GREEN),
    ]

    for i, (title, blist, col) in enumerate(pack_items):
        xp = Inches(0.8) + i * (w_pack + gap_p)
        add_card(s9, xp, top_p, w_pack, h_p, border_color=col)
        tb_p = s9.shapes.add_textbox(xp + Inches(0.15), top_p + Inches(0.15), w_pack - Inches(0.3), h_p - Inches(0.3))
        tf_p = tb_p.text_frame
        tf_p.word_wrap = True
        p = tf_p.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = col
        for b in blist:
            p = tf_p.add_paragraph()
            p.text = "• " + b
            p.font.size = Pt(11)

    s9.notes_slide.notes_text_frame.text = "Layer 5 is our Golden-Hour Recovery Pack. If fraud occurs, every second counts. In one click, our system generates an exact phone script for the 1930 Cyber Helpline with the UTR on line 1, a formal bank freeze notice, and an NCRP cybercrime portal draft."

    # ==========================================
    # SLIDE 10: STEP-BY-STEP ATTACK WALKTHROUGH
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s10, BG_LIGHT)
    add_header(s10, "Case Study: Neutralizing a ₹48.5 Lakh CEO Attack in 5 Seconds")

    steps = [
        ("Step 1: The Spoofed Email", "Scammer emails Accounts stating vendor bank account changed due to audit (from abc-l0gistics.com).", "T04 flags Look-alike Domain", ACCENT_AMBER),
        ("Step 2: The Altered Invoice", "PDF invoice attached requesting ₹48,50,000 to a new ICICI Bank account.", "T08 flags Account Mismatch vs Master", ACCENT_AMBER),
        ("Step 3: The Deepfake CEO Call", "Scammer joins Google Meet with AI-cloned voice of CFO: 'Wire ₹48.5 Lakhs immediately, confidential acquisition!'", "T07 extension triggers Red Synthetic Voice alert (94%)", ACCENT_RED),
        ("Step 4: The Automated Lock", "Policy Engine evaluates signals: multiple strong anomalies detected -> HARD HOLD. Payment transfer button disabled.", "Policy Engine forces HOLD band", ACCENT_RED),
        ("Step 5: OOB Verification", "Clerk taps 'Confirm with CFO'. Real CFO receives push notification on mobile: 'No, not me!' Case locked as FRAUD.", "₹48.5 Lakhs Saved in 5 Seconds!", ACCENT_GREEN),
    ]

    for i, (st, desc, flag, col) in enumerate(steps):
        yp = Inches(1.8) + Inches(i * 1.05)
        add_card(s10, Inches(0.8), yp, Inches(11.7), Inches(0.95))
        # left accent
        s_bar = s10.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), yp, Inches(0.15), Inches(0.95))
        s_bar.fill.solid()
        s_bar.fill.fore_color.rgb = col
        s_bar.line.fill.background()

        tb = s10.shapes.add_textbox(Inches(1.1), yp + Inches(0.08), Inches(7.5), Inches(0.8))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = st
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        p = tf.add_paragraph()
        p.text = desc
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED

        # flag pill
        pill = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.8), yp + Inches(0.2), Inches(3.5), Inches(0.55))
        pill.fill.solid()
        pill.fill.fore_color.rgb = col
        pill.line.fill.background()
        ptf = pill.text_frame
        pp = ptf.paragraphs[0]
        pp.text = flag
        pp.font.size = Pt(10)
        pp.font.bold = True
        pp.font.color.rgb = TEXT_WHITE
        pp.alignment = PP_ALIGN.CENTER

    s10.notes_slide.notes_text_frame.text = "This timeline shows our live test case. In 5 seconds, Satyapan caught the spoofed domain, detected the invoice bank mismatch, flagged the cloned voice on Meet, locked the payment button, and confirmed with the real CFO."

    # ==========================================
    # SLIDE 11: RESEARCH & BENCHMARKS (HARD NUMBERS)
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s11, BG_LIGHT)
    add_header(s11, "Empirical Validation: Hard Numbers & Benchmarks")

    metrics_data = [
        ("0.0% EER", "Google Meet Codec\n(Opus 16kHz audio)", "Zero error rate on WebRTC video call audio (n=100 items). 4.0% EER on cellular AMR-NB.", ACCENT_GREEN),
        ("0 / 30 Bypassed", "Adversarial Red-Team\nPrompt Injections", "0/30 injections lowered a security band. 97.8% checker rejection rate on malicious prompts.", ACCENT_GREEN),
        ("94.3% Recall", "ICFD-31k Large Benchmark\n@ 1% False Alarm Rate", "Evaluated on 31,000 real conversations with 10,000-resample bootstrap 95% CIs [93.5%, 95.1%].", PRIMARY),
        ("8 / 12 Upgraded", "Decision Relevance\nEnterprise Scenarios", "Detectors upgraded risk outcome from unsafe PASS to HOLD/VERIFY in 8 out of 12 real attack cases.", ACCENT_AMBER),
    ]

    m_w = Inches(2.7)
    m_gap = Inches(0.3)
    m_top = Inches(1.8)
    m_h = Inches(5.0)

    for i, (big_num, sub, desc, col) in enumerate(metrics_data):
        mx = Inches(0.8) + i * (m_w + m_gap)
        add_card(s11, mx, m_top, m_w, m_h, border_color=col)
        tb_m = s11.shapes.add_textbox(mx + Inches(0.15), m_top + Inches(0.2), m_w - Inches(0.3), m_h - Inches(0.4))
        tf_m = tb_m.text_frame
        tf_m.word_wrap = True

        p = tf_m.paragraphs[0]
        p.text = big_num
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = col
        p.alignment = PP_ALIGN.CENTER

        p = tf_m.add_paragraph()
        p.text = "\n" + sub
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        p.alignment = PP_ALIGN.CENTER

        p = tf_m.add_paragraph()
        p.text = "\n" + desc
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED

    s11.notes_slide.notes_text_frame.text = "Our work is backed by rigorous empirical benchmarks. On Google Meet codecs, our voice detector achieves 0.0% Equal Error Rate. In adversarial testing, 0 out of 30 prompt injections bypassed our policy. On 31,000 ICFD conversations, we achieve over 94% recall at 1% false alarms."

    # ==========================================
    # SLIDE 12: INDIA-FIRST & AWS ARCHITECTURE
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s12, BG_LIGHT)
    add_header(s12, "India-First Localization & AWS Mumbai Cloud Architecture")

    add_card(s12, Inches(0.8), Inches(1.8), Inches(5.7), Inches(5.0))
    tb_i = s12.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf_i = tb_i.text_frame
    tf_i.word_wrap = True
    p = tf_i.paragraphs[0]
    p.text = "🇮🇳 Tailored for Indian Ecosystem"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    i_pts = [
        "RBI .bank.in Domain Rule: Enforces Reserve Bank of India mandates requiring all legitimate bank communications to originate from .bank.in domains.",
        "Indian Accounting Native: Native regex parsers for 11-digit IFSC codes, GSTIN structure, and UPI VPA IDs.",
        "Hinglish & Regional Lexicon: Identifies cultural fraud triggers ('digital arrest', 'bijli connection', 'police FIR', 'OTP batao').",
        "National Crime Portal Alignment: Output forms align 1:1 with national 1930 Cyber Helpline & cybercrime.gov.in."
    ]
    for b in i_pts:
        p = tf_i.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)

    add_card(s12, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0))
    tb_a = s12.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf_a = tb_a.text_frame
    tf_a.word_wrap = True
    p = tf_a.paragraphs[0]
    p.text = "☁️ AWS ap-south-1 (Mumbai) Deployment"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_AMBER
    a_pts = [
        "Amazon S3 Object Lock: WORM (Write Once, Read Many) tamper-evident evidence vault compliant with court standards.",
        "Amazon Bedrock (Claude Haiku): Secure in-country AI summaries with zero training retention and strict data privacy.",
        "Amazon SES (Simple Email Service): Cryptographically signed Out-of-Band (OOB) executive verification emails.",
        "Amazon Transcribe (hi-IN / en-IN): High-fidelity regional Indian speech-to-text with local Whisper fallback."
    ]
    for b in a_pts:
        p = tf_a.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(12)

    s12.notes_slide.notes_text_frame.text = "Satyapan is built specifically for India and hosted in AWS Mumbai. It enforces RBI .bank.in domain rules, understands Hinglish fraud slang, and leverages Amazon S3 Object Lock and Bedrock for legal custody and zero data leakage."

    # ==========================================
    # SLIDE 13: STRETCH FEATURE - CITIZEN SCAM CHECK
    # ==========================================
    s13 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s13, BG_LIGHT)
    add_header(s13, "Social Impact: Citizen 'Scam Check' Mobile Web (T24)")

    add_card(s13, Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.0))
    tb_c = s13.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(11.3), Inches(4.6))
    tf_c = tb_c.text_frame
    tf_c.word_wrap = True
    p = tf_c.paragraphs[0]
    p.text = "📱 Protecting Ordinary Citizens & Families from Daily WhatsApp Fraud"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = PRIMARY

    c_pts = [
        "Mobile-First Web App (console/public/scam-check.html): Extremely lightweight, zero login, accessible on any smartphone.",
        "Paste-and-Check Interface: Users paste suspicious SMS or WhatsApp messages and receive instant coarse advice (HOLD, VERIFY, PASS).",
        "Deterministic 'Impossible Claim' Engine: Catches Digital Arrests ('CBI video call'), Electricity Disconnection threats, Customs release fees, and fake refunds.",
        "Voice Read-Aloud for Elders ('मेरे सुनाइए'): Built-in Web Speech API reads the advice aloud in Hindi (hi-IN) or English for non-literate users.",
        "Emergency Action Hub: Direct tap-to-call '1930' button, official Chakshu & NCRP links, and one-tap WhatsApp share to warn family members.",
        "Safety Architecture: Never reveals forensic scores or detector internals, preventing attackers from reverse-engineering the tool."
    ]
    for b in c_pts:
        p = tf_c.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(13)

    s13.notes_slide.notes_text_frame.text = "As a social impact extension, we built 'Scam Check' for ordinary citizens. Elders can paste suspicious WhatsApp messages, hear the advice read aloud in Hindi, and tap one button to dial the 1930 helpline."

    # ==========================================
    # SLIDE 14: CONCLUSION & ROADMAP
    # ==========================================
    s14 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s14, BG_DARK)

    tb_end = s14.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(11.7), Inches(5.2))
    tf_e = tb_end.text_frame
    tf_e.word_wrap = True

    p = tf_e.paragraphs[0]
    p.text = "Why Satyapan Wins & The Road Ahead"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = TEXT_WHITE

    p = tf_e.add_paragraph()
    p.text = "\n1. Why Satyapan Wins:"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    win_pts = [
        "Deterministic Security + AI Speed: The only system where media detectors cannot create a false sense of safety.",
        "Immediate Production Viability: Works on standard accounting exports (Tally, Zoho, SAP CSVs) with near-zero inference cost."
    ]
    for w in win_pts:
        p = tf_e.add_paragraph()
        p.text = "   • " + w
        p.font.size = Pt(13)
        p.font.color.rgb = RGBColor(226, 232, 240)

    p = tf_e.add_paragraph()
    p.text = "\n2. Future Roadmap:"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = TEXT_CYAN
    road_pts = [
        "Phase 1 (Now): Google Meet extension + React AP Verification Desk (MVP Fully Built).",
        "Phase 2 (Q3 2026): NPCI Vendor Attestation Standard (QR/UPI dynamic verification extension).",
        "Phase 3 (Q4 2026): Citizen WhatsApp Verification Bot integrated directly with I4C Chakshu."
    ]
    for r in road_pts:
        p = tf_e.add_paragraph()
        p.text = "   • " + r
        p.font.size = Pt(13)
        p.font.color.rgb = RGBColor(226, 232, 240)

    p = tf_e.add_paragraph()
    p.text = "\n🛡️ 'We don't just detect fake faces; we protect Indian enterprises where it matters most: their hard-earned money.'"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = ACCENT_AMBER

    s14.notes_slide.notes_text_frame.text = "To conclude, Satyapan provides true defense-in-depth by anchoring security to payments rather than media alone. It is practical, cost-effective, and ready for Indian enterprises today. Thank you, judges!"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    print(f"Presentation saved successfully to: {output_path}")


if __name__ == "__main__":
    out = Path("c:/Users/Admin/Hackathon/Deepfake_Detection/Satyapan_Pitch_Deck.pptx")
    create_deck(out)

