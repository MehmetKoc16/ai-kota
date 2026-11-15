using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;

namespace KotaTepsi;

public sealed class KotaPaneli : Form
{
    private const int PanelGenisligi = 360;
    private const int DisBosluk = 14;
    private const int KartIcBosluk = 12;
    private const int KartKoseYaricapi = 8;

    private static readonly Color ArkaPlanRengi = Color.FromArgb(0x20, 0x20, 0x20);
    private static readonly Color KartRengi = Color.FromArgb(0x2B, 0x2B, 0x2B);
    private static readonly Color CipZeminRengi = Color.FromArgb(0x2E, 0x2E, 0x2E);
    private static readonly Color CubukZeminRengi = Color.FromArgb(0x3A, 0x3A, 0x3A);
    private static readonly Color BirincilYaziRengi = Color.FromArgb(0xFF, 0xFF, 0xFF);
    private static readonly Color IkincilYaziRengi = Color.FromArgb(0xC5, 0xC5, 0xC5);
    private static readonly Color SolukYaziRengi = Color.FromArgb(0x8A, 0x8A, 0x8A);
    private static readonly Color TempoIsaretRengi = Color.FromArgb(0xE0, 0xE0, 0xE0);
    private static readonly Color BiterUyariRengi = Color.FromArgb(0xFF, 0xB9, 0x00);

    private static readonly string YaziTipiAdi = FontMevcutMu("Segoe UI Variable Text")
        ? "Segoe UI Variable Text"
        : "Segoe UI";

    private static readonly bool FluentIkonMevcut = FontMevcutMu("Segoe Fluent Icons");

    [DllImport("dwmapi.dll", PreserveSig = true)]
    private static extern int DwmSetWindowAttribute(
        IntPtr hwnd,
        int attr,
        ref int attrValue,
        int attrSize);

    private KotaVerisi? _veri;
    private DateTimeOffset _sonrakiYenileme = DateTimeOffset.Now.AddMinutes(5);
    private bool _yenileniyor;
    private string? _yenilemeHatasi;
    private int _icerikYuksekligi = 200;
    private int _kaydirmaY;
    private RectangleF _yenileAlani;

    public event EventHandler? YenileIstendi;

    [System.ComponentModel.DesignerSerializationVisibility(System.ComponentModel.DesignerSerializationVisibility.Hidden)]
    [System.ComponentModel.Browsable(false)]
    public bool Yenileniyor
    {
        get => _yenileniyor;
        set
        {
            if (_yenileniyor == value)
                return;
            _yenileniyor = value;
            Invalidate();
        }
    }

    [System.ComponentModel.DesignerSerializationVisibility(System.ComponentModel.DesignerSerializationVisibility.Hidden)]
    [System.ComponentModel.Browsable(false)]
    public string? YenilemeHatasi
    {
        get => _yenilemeHatasi;
        set
        {
            if (_yenilemeHatasi == value)
                return;
            _yenilemeHatasi = value;
            BoyutuVeKonumuAyarla();
            Invalidate();
        }
    }

    public KotaPaneli()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        TopMost = true;
        StartPosition = FormStartPosition.Manual;
        DoubleBuffered = true;
        BackColor = ArkaPlanRengi;
        KeyPreview = true;
        Width = PanelGenisligi;
        Height = 200;
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        try
        {
            int tercih = 2; // DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
            _ = DwmSetWindowAttribute(Handle, 33, ref tercih, sizeof(int));
        }
        catch
        {
            // Eski Windows sürümlerinde yoksay.
        }
    }

    protected override void OnDeactivate(EventArgs e)
    {
        base.OnDeactivate(e);
        Hide();
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        base.OnKeyDown(e);
        if (e.KeyCode == Keys.Escape)
        {
            e.Handled = true;
            Hide();
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Hide();
            return;
        }
        base.OnFormClosing(e);
    }

    protected override void OnMouseWheel(MouseEventArgs e)
    {
        base.OnMouseWheel(e);
        int maksKaydirma = Math.Max(0, _icerikYuksekligi - ClientSize.Height);
        if (maksKaydirma <= 0)
            return;

        int yeni = _kaydirmaY - (e.Delta / 120) * 32;
        yeni = Math.Clamp(yeni, 0, maksKaydirma);
        if (yeni != _kaydirmaY)
        {
            _kaydirmaY = yeni;
            Invalidate();
        }
    }

    protected override void OnMouseClick(MouseEventArgs e)
    {
        base.OnMouseClick(e);
        if (e.Button != MouseButtons.Left)
            return;

        var nokta = new PointF(e.X, e.Y + _kaydirmaY);
        if (_yenileAlani.Contains(nokta) && !_yenileniyor)
        {
            YenileIstendi?.Invoke(this, EventArgs.Empty);
        }
    }

    public void Guncelle(KotaVerisi? veri, DateTimeOffset sonrakiYenileme)
    {
        _veri = veri;
        _sonrakiYenileme = sonrakiYenileme;
        BoyutuVeKonumuAyarla();
        Invalidate();
    }

    public void Goster()
    {
        _kaydirmaY = 0;
        BoyutuVeKonumuAyarla();
        Show();
        Activate();
    }

    private void BoyutuVeKonumuAyarla()
    {
        var calismaAlani = Screen.FromPoint(Cursor.Position).WorkingArea;
        int maksYukseklik = Math.Max(200, (int)(calismaAlani.Height * 0.85));

        _icerikYuksekligi = IcerikYuksekligiOlc(_veri, PanelGenisligi, DateTimeOffset.Now, _sonrakiYenileme, _yenilemeHatasi);
        int hedefYukseklik = Math.Min(_icerikYuksekligi, maksYukseklik);
        int maksKaydirma = Math.Max(0, _icerikYuksekligi - hedefYukseklik);
        _kaydirmaY = Math.Clamp(_kaydirmaY, 0, maksKaydirma);

        Size = new Size(PanelGenisligi, hedefYukseklik);
        Location = new Point(
            calismaAlani.Right - Width - 12,
            calismaAlani.Bottom - Height - 12);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        e.Graphics.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        e.Graphics.Clear(ArkaPlanRengi);
        e.Graphics.TranslateTransform(0, -_kaydirmaY);

        _ = CizVeyaOlc(
            e.Graphics,
            _veri,
            ClientSize.Width,
            DateTimeOffset.Now,
            _sonrakiYenileme,
            _yenileniyor,
            _yenilemeHatasi,
            ciz: true,
            out _yenileAlani);
    }

    public static Bitmap OnizlemeCiz(KotaVerisi? veri, int genislik, DateTimeOffset simdi)
    {
        int w = Math.Max(200, genislik);
        var sonraki = simdi.AddMinutes(5);
        int h = IcerikYuksekligiOlc(veri, w, simdi, sonraki, yenilemeHatasi: null);

        var bmp = new Bitmap(w, Math.Max(100, h), System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using var g = Graphics.FromImage(bmp);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        g.Clear(ArkaPlanRengi);

        _ = CizVeyaOlc(g, veri, w, simdi, sonraki, yenileniyor: false, yenilemeHatasi: null, ciz: true, out _);
        return bmp;
    }

    private static int IcerikYuksekligiOlc(
        KotaVerisi? veri,
        int genislik,
        DateTimeOffset simdi,
        DateTimeOffset sonrakiYenileme,
        string? yenilemeHatasi)
    {
        using var gecici = new Bitmap(1, 1);
        using var g = Graphics.FromImage(gecici);
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        return CizVeyaOlc(g, veri, genislik, simdi, sonrakiYenileme, yenileniyor: false, yenilemeHatasi, ciz: false, out _);
    }

    private static int CizVeyaOlc(
        Graphics g,
        KotaVerisi? veri,
        int genislik,
        DateTimeOffset simdi,
        DateTimeOffset sonrakiYenileme,
        bool yenileniyor,
        string? yenilemeHatasi,
        bool ciz,
        out RectangleF yenileAlani)
    {
        using var baslikFont = new Font(YaziTipiAdi, 11f, FontStyle.Bold, GraphicsUnit.Point);
        using var normalFont = new Font(YaziTipiAdi, 9f, FontStyle.Regular, GraphicsUnit.Point);
        using var kalinFont = new Font(YaziTipiAdi, 9f, FontStyle.Bold, GraphicsUnit.Point);
        using var kucukFont = new Font(YaziTipiAdi, 8f, FontStyle.Regular, GraphicsUnit.Point);
        using var ikonFont = new Font(
            FluentIkonMevcut ? "Segoe Fluent Icons" : YaziTipiAdi,
            FluentIkonMevcut ? 11f : 12f,
            FontStyle.Regular,
            GraphicsUnit.Point);

        using var birincilFirca = new SolidBrush(BirincilYaziRengi);
        using var ikincilFirca = new SolidBrush(IkincilYaziRengi);
        using var solukFirca = new SolidBrush(SolukYaziRengi);
        using var biterFirca = new SolidBrush(BiterUyariRengi);
        using var kartFirca = new SolidBrush(KartRengi);
        using var cipFirca = new SolidBrush(CipZeminRengi);
        using var cubukZeminFirca = new SolidBrush(CubukZeminRengi);
        using var tempoFirca = new SolidBrush(TempoIsaretRengi);

        float icerikX = DisBosluk;
        float icerikW = genislik - 2 * DisBosluk;
        float y = DisBosluk;

        // Üst başlık + Yenile düğmesi
        const float yenileBoyut = 28f;
        yenileAlani = new RectangleF(genislik - DisBosluk - yenileBoyut, y - 2f, yenileBoyut, yenileBoyut);

        if (ciz)
        {
            g.DrawString("Yapay zekâ kotası", baslikFont, birincilFirca, icerikX, y);

            string ikonMetni = FluentIkonMevcut ? "\uE72C" : "↻";
            using var ikonFirca = new SolidBrush(yenileniyor ? SolukYaziRengi : IkincilYaziRengi);
            using var merkezFormat = new StringFormat
            {
                Alignment = StringAlignment.Center,
                LineAlignment = StringAlignment.Center,
            };
            g.DrawString(ikonMetni, ikonFont, ikonFirca, yenileAlani, merkezFormat);
        }

        y += g.MeasureString("Yapay zekâ kotası", baslikFont).Height + 2f;

        if (ciz)
        {
            g.DrawString("Codex · Claude · Gemini", kucukFont, solukFirca, icerikX, y);
        }
        y += g.MeasureString("Codex · Claude · Gemini", kucukFont).Height + 10f;

        var saglayicilar = veri?.Saglayicilar;
        if (saglayicilar is null || saglayicilar.Count == 0)
        {
            const string bosMesaj = "Kota verisi bulunamadı. Yenile düğmesine basarak veri toplayabilirsiniz.";
            var olcuAlani = new SizeF(icerikW - 2 * KartIcBosluk, 500f);
            float metinH = g.MeasureString(bosMesaj, normalFont, olcuAlani).Height;
            float kartH = metinH + 2 * KartIcBosluk;

            if (ciz)
            {
                var kartRect = new RectangleF(icerikX, y, icerikW, kartH);
                YuvarlakDoldur(g, kartFirca, kartRect, KartKoseYaricapi);
                var yaziRect = new RectangleF(icerikX + KartIcBosluk, y + KartIcBosluk, icerikW - 2 * KartIcBosluk, metinH + 4f);
                g.DrawString(bosMesaj, normalFont, ikincilFirca, yaziRect);
            }

            y += kartH + 12f;
        }
        else
        {
            // Çip satırı
            float cipX = icerikX;
            float cipY = y;
            float cipSatirH = 0f;
            const float cipAralik = 6f;

            foreach (var s in saglayicilar)
            {
                string ad = Bicim.SaglayiciAdi(s.Ad);
                bool hata = string.Equals(s.Durum, "hata", StringComparison.OrdinalIgnoreCase);
                string yuzdeMetin = hata
                    ? "–"
                    : $"%{(int)Math.Round(Bicim.EnYuksekKullanim(s), MidpointRounding.AwayFromZero)}";

                const float adYuzdeBosluk = 4f;
                SizeF adBoyut = g.MeasureString(ad, kucukFont);
                SizeF yuzdeBoyut = g.MeasureString(yuzdeMetin, kucukFont);
                float cipW = adBoyut.Width + adYuzdeBosluk + yuzdeBoyut.Width + 14f;
                float cipH = Math.Max(adBoyut.Height, yuzdeBoyut.Height) + 8f;

                if (cipX > icerikX && cipX + cipW > icerikX + icerikW)
                {
                    cipX = icerikX;
                    cipY += cipSatirH + cipAralik;
                    cipSatirH = 0f;
                }

                if (ciz)
                {
                    var cipRect = new RectangleF(cipX, cipY, cipW, cipH);
                    YuvarlakDoldur(g, cipFirca, cipRect, cipH / 2f);

                    float yaziY = cipY + 4f;
                    g.DrawString(ad, kucukFont, ikincilFirca, cipX + 7f, yaziY);

                    Color renk = hata ? SolukYaziRengi : Bicim.EtiketRengi(s.Etiket);
                    using var renkFirca = new SolidBrush(renk);
                    g.DrawString(yuzdeMetin, kucukFont, renkFirca, cipX + 7f + adBoyut.Width + adYuzdeBosluk, yaziY);
                }

                cipX += cipW + cipAralik;
                cipSatirH = Math.Max(cipSatirH, cipH);
            }

            y = cipY + cipSatirH + 12f;

            // Sağlayıcı kartları
            foreach (var s in saglayicilar)
            {
                float kartBasY = y;
                float icY = kartBasY + KartIcBosluk;
                float icX = icerikX + KartIcBosluk;
                float icW = icerikW - 2 * KartIcBosluk;

                string ad = Bicim.SaglayiciAdi(s.Ad);
                bool bayat = string.Equals(s.Durum, "bayat", StringComparison.OrdinalIgnoreCase);
                bool hata = string.Equals(s.Durum, "hata", StringComparison.OrdinalIgnoreCase);
                Color etiketRenk = Bicim.EtiketRengi(s.Etiket);

                SizeF adBoyut = g.MeasureString(ad, kalinFont);
                string etiketMetin = string.IsNullOrWhiteSpace(s.Etiket) ? (hata ? "hata" : "–") : s.Etiket!;
                SizeF etiketBoyut = g.MeasureString(etiketMetin, kucukFont);

                // Kart içeriğini önce hesapla / çiz
                float baslikSatirH = Math.Max(adBoyut.Height, etiketBoyut.Height + 6f);
                float icerikYukseklik = baslikSatirH;

                var pencereler = s.Pencereler is { Count: > 0 }
                    ? s.Pencereler
                        .OrderBy(p => Bicim.PencereSirasi(p.Ad))
                        .ThenBy(p => p.Ad ?? string.Empty, StringComparer.OrdinalIgnoreCase)
                        .ToList()
                    : null;
                if (hata)
                {
                    string hataMetin = string.IsNullOrWhiteSpace(s.Hata) ? "Veri okunamadı." : s.Hata!;
                    float hataH = g.MeasureString(hataMetin, normalFont, new SizeF(icW, 400f)).Height;
                    icerikYukseklik += 8f + hataH;
                }
                else if (pencereler is not null && pencereler.Count > 0)
                {
                    foreach (var p in pencereler)
                    {
                        icerikYukseklik += 10f;
                        string pencereAd = Bicim.PencereAdi(p.Ad);
                        float satirH = g.MeasureString(pencereAd, normalFont).Height;
                        icerikYukseklik += satirH + 4f + 6f; // çubuk 6 px

                        if (p.Tempo?.Biter == true && p.Tempo.Bitis is not null)
                        {
                            float biterH = g.MeasureString("~1sa'da biter", kucukFont).Height;
                            icerikYukseklik += 4f + biterH;
                        }
                    }
                }

                float kartH = KartIcBosluk + icerikYukseklik + KartIcBosluk;

                if (ciz)
                {
                    var kartRect = new RectangleF(icerikX, kartBasY, icerikW, kartH);
                    YuvarlakDoldur(g, kartFirca, kartRect, KartKoseYaricapi);

                    // Sağlayıcı adı + (bayat)
                    g.DrawString(ad, kalinFont, birincilFirca, icX, icY);
                    if (bayat)
                    {
                        g.DrawString("(bayat)", kucukFont, solukFirca, icX + adBoyut.Width + 4f, icY + 1f);
                    }

                    // Sağda etiket hapı
                    float hapW = etiketBoyut.Width + 14f;
                    float hapH = etiketBoyut.Height + 6f;
                    var hapRect = new RectangleF(icX + icW - hapW, icY - 1f, hapW, hapH);
                    using var hapZemin = new SolidBrush(Color.FromArgb(40, etiketRenk));
                    using var hapKalem = new Pen(Color.FromArgb(140, etiketRenk), 1f);
                    using var etiketFirca = new SolidBrush(hata ? SolukYaziRengi : etiketRenk);
                    YuvarlakDoldur(g, hapZemin, hapRect, hapH / 2f);
                    YuvarlakCiz(g, hapKalem, hapRect, hapH / 2f);

                    using var merkezFmt = new StringFormat
                    {
                        Alignment = StringAlignment.Center,
                        LineAlignment = StringAlignment.Center,
                    };
                    g.DrawString(etiketMetin, kucukFont, etiketFirca, hapRect, merkezFmt);
                }

                icY += baslikSatirH;

                if (hata)
                {
                    icY += 8f;
                    string hataMetin = string.IsNullOrWhiteSpace(s.Hata) ? "Veri okunamadı." : s.Hata!;
                    float hataH = g.MeasureString(hataMetin, normalFont, new SizeF(icW, 400f)).Height;
                    if (ciz)
                    {
                        g.DrawString(hataMetin, normalFont, solukFirca, new RectangleF(icX, icY, icW, hataH + 4f));
                    }
                    icY += hataH;
                }
                else if (pencereler is not null)
                {
                    foreach (var p in pencereler)
                    {
                        icY += 10f;
                        string pencereAd = Bicim.PencereAdi(p.Ad);
                        int yuzdeTam = (int)Math.Round(p.Kullanilan, MidpointRounding.AwayFromZero);
                        string sagMetin = p.Sifirlanma is not null
                            ? $"%{yuzdeTam} · {Bicim.SureMetni(p.Sifirlanma.Value - simdi)}"
                            : $"%{yuzdeTam}";

                        float satirH = g.MeasureString(pencereAd, normalFont).Height;
                        if (ciz)
                        {
                            g.DrawString(pencereAd, normalFont, ikincilFirca, icX, icY);
                            using var sagFmt = new StringFormat { Alignment = StringAlignment.Far };
                            g.DrawString(sagMetin, normalFont, ikincilFirca, new RectangleF(icX, icY, icW, satirH + 2f), sagFmt);
                        }
                        icY += satirH + 4f;

                        // 6 px yuvarlak çubuk
                        const float cubukH = 6f;
                        if (ciz)
                        {
                            var zeminRect = new RectangleF(icX, icY, icW, cubukH);
                            YuvarlakDoldur(g, cubukZeminFirca, zeminRect, 3f);

                            double oran = Math.Clamp(p.Kullanilan / 100.0, 0.0, 1.0);
                            float dolguW = (float)(icW * oran);
                            if (dolguW > 0.5f)
                            {
                                var dolguRect = new RectangleF(icX, icY, Math.Max(cubukH, Math.Min(icW, dolguW)), cubukH);
                                using var dolguFirca = new SolidBrush(etiketRenk);
                                YuvarlakDoldur(g, dolguFirca, dolguRect, 3f);
                            }

                            if (p.Tempo?.GecenOran is not null)
                            {
                                double gecen = Math.Clamp(p.Tempo.GecenOran.Value, 0.0, 1.0);
                                float isaretX = icX + (float)(icW * gecen) - 1f;
                                isaretX = Math.Clamp(isaretX, icX, icX + icW - 2f);
                                g.FillRectangle(tempoFirca, isaretX, icY - 1f, 2f, cubukH + 2f);
                            }
                        }
                        icY += cubukH;

                        if (p.Tempo?.Biter == true && p.Tempo.Bitis is not null)
                        {
                            icY += 4f;
                            string biterMetin = $"~{Bicim.SureMetni(p.Tempo.Bitis.Value - simdi)}'da biter";
                            float biterH = g.MeasureString(biterMetin, kucukFont).Height;
                            if (ciz)
                            {
                                g.DrawString(biterMetin, kucukFont, biterFirca, icX, icY);
                            }
                            icY += biterH;
                        }
                    }
                }

                y = kartBasY + kartH + 8f;
            }
        }

        // Alt bilgi satırı
        string guncellendiMetin = veri?.Olusturma is not null
            ? veri.Olusturma.Value.ToLocalTime().ToString("HH:mm")
            : "–";
        TimeSpan kalanOto = sonrakiYenileme - simdi;
        int kalanDk = Math.Max(0, (int)Math.Ceiling(kalanOto.TotalMinutes));
        string altMetin = $"güncellendi {guncellendiMetin} · sonraki {kalanDk}dk";

        if (ciz)
        {
            g.DrawString(altMetin, kucukFont, solukFirca, icerikX, y);
        }
        y += g.MeasureString(altMetin, kucukFont).Height;

        if (!string.IsNullOrWhiteSpace(yenilemeHatasi))
        {
            y += 2f;
            if (ciz)
            {
                g.DrawString(yenilemeHatasi, kucukFont, solukFirca, icerikX, y);
            }
            y += g.MeasureString(yenilemeHatasi, kucukFont).Height;
        }

        y += DisBosluk;

        return (int)Math.Ceiling(y);
    }

    private static void YuvarlakDoldur(Graphics g, Brush firca, RectangleF rect, float yaricap)
    {
        if (rect.Width <= 0 || rect.Height <= 0)
            return;

        float r = Math.Min(yaricap, Math.Min(rect.Width, rect.Height) / 2f);
        if (r <= 0.5f)
        {
            g.FillRectangle(firca, rect);
            return;
        }

        using var yol = YuvarlakYol(rect, r);
        g.FillPath(firca, yol);
    }

    private static void YuvarlakCiz(Graphics g, Pen kalem, RectangleF rect, float yaricap)
    {
        if (rect.Width <= 0 || rect.Height <= 0)
            return;

        float r = Math.Min(yaricap, Math.Min(rect.Width, rect.Height) / 2f);
        if (r <= 0.5f)
        {
            g.DrawRectangle(kalem, rect.X, rect.Y, rect.Width, rect.Height);
            return;
        }

        using var yol = YuvarlakYol(rect, r);
        g.DrawPath(kalem, yol);
    }

    private static GraphicsPath YuvarlakYol(RectangleF rect, float r)
    {
        float d = r * 2f;
        var yol = new GraphicsPath();
        yol.AddArc(rect.X, rect.Y, d, d, 180, 90);
        yol.AddArc(rect.Right - d, rect.Y, d, d, 270, 90);
        yol.AddArc(rect.Right - d, rect.Bottom - d, d, d, 0, 90);
        yol.AddArc(rect.X, rect.Bottom - d, d, d, 90, 90);
        yol.CloseFigure();
        return yol;
    }

    private static bool FontMevcutMu(string aileAdi)
    {
        try
        {
            foreach (var aile in FontFamily.Families)
            {
                if (string.Equals(aile.Name, aileAdi, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
        }
        catch
        {
            // Yoksay
        }
        return false;
    }
}
