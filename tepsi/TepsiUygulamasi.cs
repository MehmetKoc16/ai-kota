using System.Diagnostics;
using System.Drawing;
using Microsoft.Win32;

namespace KotaTepsi;

public sealed class TepsiUygulamasi : ApplicationContext
{
    private const string KayitDefteriRunYolu = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string KayitDefteriDegerAdi = "KotaTepsi";

    private readonly string _veriDizini;
    private readonly string _kotaJsonYolu;
    private readonly KotaPaneli _panel;
    private readonly NotifyIcon _tepsiSimgesi;
    private readonly ContextMenuStrip _baglamMenusu;
    private readonly ToolStripMenuItem _otomatikBaslatOgeleri;
    private readonly System.Windows.Forms.Timer _dosyaDebounceTimer;
    private readonly System.Windows.Forms.Timer _otoYenileTimer;
    private readonly System.Windows.Forms.Timer _dakikaTimer;
    private readonly FileSystemWatcher? _izleyici;

    private Icon? _mevcutSimge;
    private KotaVerisi? _sonVeri;
    private DateTimeOffset _sonrakiYenileme = DateTimeOffset.Now.AddMinutes(5);
    private string? _yenilemeHatasi;
    private bool _yenileniyor;
    private DateTime _claudeYazmaZamani;
    private DateTimeOffset? _claudeSifirlanma;
    private bool _kapatiliyor;

    public TepsiUygulamasi()
    {
        _veriDizini = VeriDiziniBul();
        _kotaJsonYolu = Path.Combine(_veriDizini, "kota.json");

        _panel = new KotaPaneli();
        _ = _panel.Handle; // BeginInvoke için handle'ın oluşturulduğundan emin ol.
        _panel.YenileIstendi += (_, _) => YenilemeyiBaslat();

        _otomatikBaslatOgeleri = new ToolStripMenuItem("Windows açılışında başlat")
        {
            CheckOnClick = true,
            Checked = AcilistaBaslatAktifMi(),
        };
        _otomatikBaslatOgeleri.CheckedChanged += (_, _) =>
            AcilistaBaslatAyarla(_otomatikBaslatOgeleri.Checked);

        var simdiYenile = new ToolStripMenuItem("Şimdi yenile");
        simdiYenile.Click += (_, _) => YenilemeyiBaslat();

        var cikis = new ToolStripMenuItem("Çık");
        cikis.Click += (_, _) => CikisYap();

        _baglamMenusu = new ContextMenuStrip
        {
            Renderer = new ToolStripProfessionalRenderer(new KoyuMenuRenkTablosu()),
            ForeColor = Color.White,
            BackColor = Color.FromArgb(0x2B, 0x2B, 0x2B),
            ShowImageMargin = false,
        };
        _baglamMenusu.Items.Add(simdiYenile);
        _baglamMenusu.Items.Add(_otomatikBaslatOgeleri);
        _baglamMenusu.Items.Add(new ToolStripSeparator());
        _baglamMenusu.Items.Add(cikis);

        _mevcutSimge = SimgeCizici.Ciz(null);
        _tepsiSimgesi = new NotifyIcon
        {
            Icon = _mevcutSimge,
            Text = "Kota verisi yok",
            ContextMenuStrip = _baglamMenusu,
            Visible = true,
        };
        _tepsiSimgesi.MouseClick += TepsiSimgesi_MouseClick;

        _dosyaDebounceTimer = new System.Windows.Forms.Timer { Interval = 500 };
        _dosyaDebounceTimer.Tick += (_, _) =>
        {
            _dosyaDebounceTimer.Stop();
            VeriyiYenidenYukle();
        };

        _claudeYazmaZamani = ClaudeSonYazmaZamani();
        _otoYenileTimer = new System.Windows.Forms.Timer { Interval = 5000 };
        _otoYenileTimer.Tick += (_, _) =>
        {
            if (_yenileniyor)
                return;
            var simdi = DateTimeOffset.Now;
            var yazma = ClaudeSonYazmaZamani();
            if (yazma != _claudeYazmaZamani || simdi >= _sonrakiYenileme || simdi >= _claudeSifirlanma)
            {
                _claudeYazmaZamani = yazma;
                _claudeSifirlanma = null;
                YenilemeyiBaslat();
            }
        };
        _otoYenileTimer.Start();

        _dakikaTimer = new System.Windows.Forms.Timer { Interval = 60 * 1000 };
        _dakikaTimer.Tick += (_, _) =>
        {
            if (_panel.Visible)
                _panel.Invalidate();
        };
        _panel.VisibleChanged += (_, _) =>
        {
            if (_panel.Visible)
                _dakikaTimer.Start();
            else
                _dakikaTimer.Stop();
        };

        _izleyici = IzleyiciOlustur(_veriDizini);

        VeriyiYenidenYukle();
        YenilemeyiBaslat();
    }

    private void TepsiSimgesi_MouseClick(object? sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left)
            return;

        if (_panel.Visible)
        {
            _panel.Hide();
        }
        else
        {
            _panel.Guncelle(_sonVeri, _sonrakiYenileme);
            _panel.Goster();
        }
    }

    private FileSystemWatcher? IzleyiciOlustur(string dizin)
    {
        try
        {
            Directory.CreateDirectory(dizin);
            var izleyici = new FileSystemWatcher(dizin, "kota.json")
            {
                NotifyFilter = NotifyFilters.FileName
                    | NotifyFilters.LastWrite
                    | NotifyFilters.CreationTime
                    | NotifyFilters.Size,
                IncludeSubdirectories = false,
                EnableRaisingEvents = true,
            };
            izleyici.Changed += DosyaDegisti;
            izleyici.Created += DosyaDegisti;
            izleyici.Renamed += DosyaDegisti;
            return izleyici;
        }
        catch
        {
            return null;
        }
    }

    private void DosyaDegisti(object sender, FileSystemEventArgs e)
    {
        if (_kapatiliyor || !_panel.IsHandleCreated)
            return;

        try
        {
            _panel.BeginInvoke(() =>
            {
                if (_kapatiliyor)
                    return;
                _dosyaDebounceTimer.Stop();
                _dosyaDebounceTimer.Start();
            });
        }
        catch
        {
            // Form kapatılırken yoksay.
        }
    }

    private static DateTime ClaudeSonYazmaZamani()
    {
        string dosya = "plan-usage-history.json";
        string kok = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Claude-Data");
        string roaming = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Claude", dosya);
        try
        {
            var son = File.GetLastWriteTimeUtc(roaming);
            if (Directory.Exists(kok))
                foreach (var dizin in Directory.EnumerateDirectories(kok, "claude_*"))
                {
                    var zaman = File.GetLastWriteTimeUtc(Path.Combine(dizin, dosya));
                    if (zaman > son)
                        son = zaman;
                }
            return son;
        }
        catch (IOException) { return DateTime.MinValue; }
        catch (UnauthorizedAccessException) { return DateTime.MinValue; }
    }

    private void VeriyiYenidenYukle()
    {
        _sonVeri = KotaVerisi.Oku(_kotaJsonYolu);
        _claudeSifirlanma = _sonVeri?.Saglayicilar?.FirstOrDefault(s => s.Ad == "claude")
            ?.Pencereler?.Select(p => p.Sifirlanma)
            .Where(zaman => zaman > _sonVeri.Olusturma).Min();

        var yeniSimge = SimgeCizici.Ciz(_sonVeri);
        var eskiSimge = _mevcutSimge;
        _mevcutSimge = yeniSimge;
        _tepsiSimgesi.Icon = yeniSimge;
        eskiSimge?.Dispose();

        _tepsiSimgesi.Text = Bicim.IpucuMetni(_sonVeri);
        _panel.Guncelle(_sonVeri, _sonrakiYenileme);
    }

    private void YenilemeyiBaslat()
    {
        if (_yenileniyor || _kapatiliyor)
            return;

        string? kotaPyYolu = KotaPyYolunuBul();
        if (kotaPyYolu is null)
        {
            _yenilemeHatasi = "kota.py bulunamadı (KOTA_PY ayarlayın)";
            _panel.YenilemeHatasi = _yenilemeHatasi;
            return;
        }

        _yenilemeHatasi = null;
        _panel.YenilemeHatasi = null;
        _yenileniyor = true;
        _panel.Yenileniyor = true;

        _ = Task.Run(() =>
        {
            try
            {
                var baslangic = new ProcessStartInfo
                {
                    FileName = "python.exe",
                    Arguments = $"\"{kotaPyYolu}\" --yaz",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                };
                using var surec = Process.Start(baslangic);
                if (surec is not null && !surec.WaitForExit(90_000))
                {
                    try
                    {
                        surec.Kill(entireProcessTree: true);
                    }
                    catch
                    {
                        // Yoksay
                    }
                }
            }
            catch
            {
                // Yoksay; mevcut veri korunur.
            }
            finally
            {
                if (!_kapatiliyor && _panel.IsHandleCreated)
                {
                    try
                    {
                        _panel.BeginInvoke(() =>
                        {
                            if (_kapatiliyor)
                                return;
                            _yenileniyor = false;
                            _panel.Yenileniyor = false;
                            _sonrakiYenileme = DateTimeOffset.Now.AddMinutes(5);
                            VeriyiYenidenYukle();
                        });
                    }
                    catch
                    {
                        // Yoksay
                    }
                }
            }
        });
    }

    public static string VeriDiziniBul()
    {
        string? ozel = Environment.GetEnvironmentVariable("KOTA_DIZIN");
        if (!string.IsNullOrWhiteSpace(ozel))
            return ozel;

        string? localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        if (string.IsNullOrWhiteSpace(localAppData))
            localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

        return Path.Combine(localAppData, "kota");
    }

    private static string? KotaPyYolunuBul()
    {
        string? envYol = Environment.GetEnvironmentVariable("KOTA_PY");
        if (!string.IsNullOrWhiteSpace(envYol) && File.Exists(envYol))
            return envYol;

        var dizin = new DirectoryInfo(AppContext.BaseDirectory);
        for (int i = 0; i < 6 && dizin is not null; i++)
        {
            string aday = Path.Combine(dizin.FullName, "kota.py");
            if (File.Exists(aday))
                return aday;
            dizin = dizin.Parent;
        }

        return null;
    }

    private static bool AcilistaBaslatAktifMi()
    {
        try
        {
            using var anahtar = Registry.CurrentUser.OpenSubKey(KayitDefteriRunYolu, writable: false);
            return anahtar?.GetValue(KayitDefteriDegerAdi) is string deger && !string.IsNullOrWhiteSpace(deger);
        }
        catch
        {
            return false;
        }
    }

    private static void AcilistaBaslatAyarla(bool aktif)
    {
        try
        {
            using var anahtar = Registry.CurrentUser.OpenSubKey(KayitDefteriRunYolu, writable: true);
            if (anahtar is null)
                return;

            if (aktif)
            {
                string? exeYolu = Environment.ProcessPath;
                if (!string.IsNullOrWhiteSpace(exeYolu))
                    anahtar.SetValue(KayitDefteriDegerAdi, $"\"{exeYolu}\"");
            }
            else
            {
                anahtar.DeleteValue(KayitDefteriDegerAdi, throwOnMissingValue: false);
            }
        }
        catch
        {
            // Yoksay
        }
    }

    private void CikisYap()
    {
        _kapatiliyor = true;
        _tepsiSimgesi.Visible = false;
        Dispose();
        Application.Exit();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _kapatiliyor = true;
            _dosyaDebounceTimer.Stop();
            _dosyaDebounceTimer.Dispose();
            _otoYenileTimer.Stop();
            _otoYenileTimer.Dispose();
            _dakikaTimer.Stop();
            _dakikaTimer.Dispose();

            if (_izleyici is not null)
            {
                _izleyici.EnableRaisingEvents = false;
                _izleyici.Dispose();
            }

            _tepsiSimgesi.Visible = false;
            _tepsiSimgesi.Dispose();
            _mevcutSimge?.Dispose();
            _baglamMenusu.Dispose();
            _panel.Dispose();
        }
        base.Dispose(disposing);
    }

    private sealed class KoyuMenuRenkTablosu : ProfessionalColorTable
    {
        private static readonly Color Zemin = Color.FromArgb(0x2B, 0x2B, 0x2B);
        private static readonly Color Secili = Color.FromArgb(0x3D, 0x3D, 0x3D);
        private static readonly Color Kenarlik = Color.FromArgb(0x45, 0x45, 0x45);

        public override Color ToolStripDropDownBackground => Zemin;
        public override Color MenuBorder => Kenarlik;
        public override Color MenuItemBorder => Secili;
        public override Color MenuItemSelected => Secili;
        public override Color MenuItemSelectedGradientBegin => Secili;
        public override Color MenuItemSelectedGradientEnd => Secili;
        public override Color MenuItemPressedGradientBegin => Secili;
        public override Color MenuItemPressedGradientEnd => Secili;
        public override Color ImageMarginGradientBegin => Zemin;
        public override Color ImageMarginGradientMiddle => Zemin;
        public override Color ImageMarginGradientEnd => Zemin;
        public override Color SeparatorDark => Kenarlik;
        public override Color SeparatorLight => Kenarlik;
    }
}
