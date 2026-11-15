using System.Drawing;
using System.Text.Json;
using KotaTepsi;
using Xunit;

namespace KotaTepsi.Tests;

public sealed class Testler
{
    private const string OrnekJson = """
    {
      "olusturma": "2026-11-15T16:15:34+03:00",
      "saglayicilar": [
        {
          "ad": "codex",
          "aile": "codex",
          "durum": "ok",
          "hata": null,
          "veri_zamani": "2026-11-15T16:03:06+03:00",
          "etiket": "dar",
          "sifirlama_hakki": null,
          "pencereler": [
            {
              "ad": "5s",
              "kullanilan": 48.0,
              "sifirlanma": "2026-11-15T17:59:59+03:00",
              "pencere_dk": 300,
              "tempo": { "gecen_oran": 0.652, "sifirlanmada_tahmin": 73.6, "biter": false, "bitis": null }
            },
            {
              "ad": "haftalik",
              "kullanilan": 82.0,
              "sifirlanma": "2026-11-18T17:04:09+03:00",
              "pencere_dk": 10080,
              "tempo": { "gecen_oran": 0.5666, "sifirlanmada_tahmin": 144.7, "biter": true, "bitis": "2026-11-16T13:09:18+03:00" }
            }
          ]
        },
        {
          "ad": "claude",
          "aile": "claude",
          "durum": "ok",
          "hata": null,
          "veri_zamani": "2026-11-15T16:15:34+03:00",
          "etiket": "dar",
          "sifirlama_hakki": null,
          "pencereler": [
            { "ad": "5s", "kullanilan": 41.0 },
            { "ad": "haftalik", "kullanilan": 81.0 },
            { "ad": "haftalik-fable", "kullanilan": 88.0 }
          ]
        },
        {
          "ad": "gemini",
          "aile": "agy",
          "durum": "ok",
          "hata": null,
          "veri_zamani": "2026-11-15T16:15:34+03:00",
          "etiket": "bol",
          "sifirlama_hakki": null,
          "pencereler": [
            { "ad": "haftalik", "kullanilan": 3.1 },
            { "ad": "5s", "kullanilan": 6.4 }
          ]
        },
        {
          "ad": "argon",
          "aile": "agy",
          "durum": "ok",
          "hata": null,
          "veri_zamani": "2026-11-15T16:15:34+03:00",
          "etiket": "bol",
          "sifirlama_hakki": null,
          "pencereler": [
            { "ad": "haftalik", "kullanilan": 1.0 }
          ]
        },
        {
          "ad": "agy-claude-gpt",
          "aile": "agy",
          "durum": "ok",
          "hata": null,
          "veri_zamani": "2026-11-15T16:15:34+03:00",
          "etiket": "bol",
          "sifirlama_hakki": null,
          "pencereler": [
            { "ad": "haftalik", "kullanilan": 0.0 },
            { "ad": "5s", "kullanilan": 0.0 }
          ]
        }
      ]
    }
    """;

    [Theory]
    [InlineData(0, "şimdi")]
    [InlineData(-15, "şimdi")]
    [InlineData(59, "0dk")]
    [InlineData(3600, "1sa 0dk")]
    [InlineData(23 * 3600 + 59 * 60, "23sa 59dk")]
    [InlineData(25 * 3600, "1g 1sa")]
    public void SureMetniSinirlariDogru(int saniye, string beklenen)
    {
        string sonuc = Bicim.SureMetni(TimeSpan.FromSeconds(saniye));
        Assert.Equal(beklenen, sonuc);
    }

    [Theory]
    [InlineData("5s", "5 saat")]
    [InlineData("haftalik", "Haftalık")]
    [InlineData("haftalik-fable", "Haftalık · Fable")]
    public void PencereAdiBicimlendirmeDogru(string girdi, string beklenen)
    {
        Assert.Equal(beklenen, Bicim.PencereAdi(girdi));
    }

    [Theory]
    [InlineData("5s", 0)]
    [InlineData("haftalik", 1)]
    [InlineData("haftalik-fable", 2)]
    [InlineData("haftalik-sonnet", 2)]
    [InlineData("aylik", 3)]
    [InlineData("", 3)]
    [InlineData(null, 3)]
    public void PencereSirasiDogru(string? girdi, int beklenen)
    {
        Assert.Equal(beklenen, Bicim.PencereSirasi(girdi));
    }

    [Fact]
    public void PencerelerSiralanincaOnce5sSonraHaftalikSonraAltHaftalikGelir()
    {
        string[] giris = ["haftalik-sonnet", "diger", "haftalik", "haftalik-fable", "5s"];
        string[] sirali = giris
            .OrderBy(Bicim.PencereSirasi)
            .ThenBy(ad => ad, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        Assert.Equal(["5s", "haftalik", "haftalik-fable", "haftalik-sonnet", "diger"], sirali);
    }

    [Fact]
    public void EtiketRengiVeBilinmeyenDogru()
    {
        Assert.Equal(Color.FromArgb(0x3F, 0xB9, 0x50), Bicim.EtiketRengi("bol"));
        Assert.Equal(Color.FromArgb(0x4C, 0xC2, 0xFF), Bicim.EtiketRengi("normal"));
        Assert.Equal(Color.FromArgb(0xFF, 0xB9, 0x00), Bicim.EtiketRengi("dar"));
        Assert.Equal(Color.FromArgb(0xFF, 0x6B, 0x6B), Bicim.EtiketRengi("dolu"));
        Assert.Equal(Color.FromArgb(0x8A, 0x8A, 0x8A), Bicim.EtiketRengi("bilinmeyen"));
        Assert.Equal(Color.FromArgb(0x8A, 0x8A, 0x8A), Bicim.EtiketRengi(null));
    }

    [Fact]
    public void EnKritikOrnekVerideDarSecerVeHepsiHataIkenNull()
    {
        var veri = JsonSerializer.Deserialize<KotaVerisi>(OrnekJson)!;
        var kritik = Bicim.EnKritik(veri);

        Assert.NotNull(kritik);
        Assert.Equal("dar", kritik!.Value.Saglayici.Etiket);
        Assert.True(kritik.Value.Saglayici.Ad is "claude" or "codex");
        Assert.Equal(88.0, kritik.Value.EnYuksekYuzde);

        var hepsiHata = new KotaVerisi
        {
            Saglayicilar =
            [
                new SaglayiciVerisi { Ad = "codex", Durum = "hata", Etiket = "dar" },
                new SaglayiciVerisi { Ad = "claude", Durum = "hata", Etiket = "dolu" },
            ]
        };
        Assert.Null(Bicim.EnKritik(hepsiHata));
    }

    [Fact]
    public void IpucuMetniOrnekVeUzunlukSiniriDogru()
    {
        var veri = JsonSerializer.Deserialize<KotaVerisi>(OrnekJson)!;
        string ipucu = Bicim.IpucuMetni(veri);

        Assert.Contains("Codex %82", ipucu);
        Assert.Contains("Claude %88", ipucu);
        Assert.Contains("Gemini %6", ipucu);
        Assert.DoesNotContain("Argon", ipucu);
        Assert.DoesNotContain("agy Claude/GPT", ipucu);

        var uzunVeri = new KotaVerisi { Saglayicilar = [] };
        for (int i = 0; i < 20; i++)
        {
            uzunVeri.Saglayicilar.Add(new SaglayiciVerisi
            {
                Ad = $"saglayici-cok-uzun-isim-{i}",
                Durum = "ok",
                Pencereler = [new PencereVerisi { Ad = "5s", Kullanilan = 50 }]
            });
        }

        string uzunIpucu = Bicim.IpucuMetni(uzunVeri);
        Assert.Equal(127, uzunIpucu.Length);
        Assert.EndsWith("…", uzunIpucu);
    }

    [Fact]
    public void KotaVerisiOkuGecerliVeBozukDosya()
    {
        string gecici = Path.Combine(Path.GetTempPath(), $"kota_test_{Guid.NewGuid():N}.json");
        string bozuk = Path.Combine(Path.GetTempPath(), $"kota_bozuk_{Guid.NewGuid():N}.json");
        try
        {
            File.WriteAllText(gecici, OrnekJson);
            var veri = KotaVerisi.Oku(gecici);

            Assert.NotNull(veri);
            Assert.NotNull(veri!.Saglayicilar);
            Assert.Equal(5, veri.Saglayicilar!.Count);

            var codex = veri.Saglayicilar.Single(s => s.Ad == "codex");
            var haftalik = codex.Pencereler!.Single(p => p.Ad == "haftalik");
            Assert.Equal(82.0, haftalik.Kullanilan);

            File.WriteAllText(bozuk, "{ bozuk json");
            Assert.Null(KotaVerisi.Oku(bozuk));
            Assert.Null(KotaVerisi.Oku(gecici + ".yok"));
        }
        finally
        {
            if (File.Exists(gecici)) File.Delete(gecici);
            if (File.Exists(bozuk)) File.Delete(bozuk);
        }
    }

    [Fact]
    public void OnizlemeCizVeriVarkenVeNullIkenBitmapDondurur()
    {
        var veri = JsonSerializer.Deserialize<KotaVerisi>(OrnekJson)!;
        using var bmp1 = KotaPaneli.OnizlemeCiz(veri, 360, DateTimeOffset.Parse("2026-11-15T16:18:00+03:00"));
        Assert.NotNull(bmp1);
        Assert.Equal(360, bmp1.Width);
        Assert.True(bmp1.Height > 100);

        using var bmp2 = KotaPaneli.OnizlemeCiz(null, 360, DateTimeOffset.Now);
        Assert.NotNull(bmp2);
        Assert.Equal(360, bmp2.Width);
        Assert.True(bmp2.Height >= 100);
    }
}
