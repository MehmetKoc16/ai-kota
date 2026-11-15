using System.Drawing;
using System.Globalization;

namespace KotaTepsi;

public static class Bicim
{
    private static readonly string[] IpucuHaricSaglayicilar = ["agy-claude-gpt", "argon"];

    public static string SureMetni(TimeSpan sure)
    {
        if (sure <= TimeSpan.Zero)
            return "şimdi";

        if (sure.TotalHours < 1.0)
            return $"{(int)sure.TotalMinutes}dk";

        if (sure.TotalDays < 1.0)
            return $"{(int)sure.TotalHours}sa {sure.Minutes}dk";

        return $"{(int)sure.TotalDays}g {sure.Hours}sa";
    }

    public static string PencereAdi(string? ad)
    {
        if (string.IsNullOrEmpty(ad))
            return string.Empty;

        if (ad == "5s")
            return "5 saat";

        if (ad == "haftalik")
            return "Haftalık";

        const string onek = "haftalik-";
        if (ad.StartsWith(onek, StringComparison.OrdinalIgnoreCase) && ad.Length > onek.Length)
        {
            string ek = ad[onek.Length..];
            string basHarf = char.ToUpper(ek[0], CultureInfo.InvariantCulture).ToString();
            return $"Haftalık · {basHarf}{ek[1..]}";
        }

        return ad;
    }

    public static int PencereSirasi(string? ad)
    {
        if (string.IsNullOrEmpty(ad))
            return 3;

        if (string.Equals(ad, "5s", StringComparison.OrdinalIgnoreCase))
            return 0;

        if (string.Equals(ad, "haftalik", StringComparison.OrdinalIgnoreCase))
            return 1;

        if (ad.StartsWith("haftalik-", StringComparison.OrdinalIgnoreCase))
            return 2;

        return 3;
    }

    public static string SaglayiciAdi(string? ad)
    {
        return ad switch
        {
            "codex" => "Codex",
            "claude" => "Claude",
            "gemini" => "Gemini",
            "argon" => "Argon",
            "agy-claude-gpt" => "agy Claude/GPT",
            null => string.Empty,
            _ => ad,
        };
    }

    public static Color EtiketRengi(string? etiket)
    {
        return etiket switch
        {
            "bol" => Color.FromArgb(0x3F, 0xB9, 0x50),
            "normal" => Color.FromArgb(0x4C, 0xC2, 0xFF),
            "dar" => Color.FromArgb(0xFF, 0xB9, 0x00),
            "dolu" => Color.FromArgb(0xFF, 0x6B, 0x6B),
            _ => Color.FromArgb(0x8A, 0x8A, 0x8A),
        };
    }

    public static int EtiketSirasi(string? etiket)
    {
        return etiket switch
        {
            "bol" => 0,
            "normal" => 1,
            "dar" => 2,
            "dolu" => 3,
            _ => -1,
        };
    }

    public static (SaglayiciVerisi Saglayici, double EnYuksekYuzde)? EnKritik(KotaVerisi? veri)
    {
        if (veri?.Saglayicilar is null || veri.Saglayicilar.Count == 0)
            return null;

        SaglayiciVerisi? enIyi = null;
        int enIyiSira = int.MinValue;
        double enIyiYuzde = double.MinValue;

        foreach (var s in veri.Saglayicilar)
        {
            if (string.Equals(s.Durum, "hata", StringComparison.OrdinalIgnoreCase))
                continue;

            int sira = EtiketSirasi(s.Etiket);
            double maksYuzde = EnYuksekKullanim(s);

            if (enIyi is null || sira > enIyiSira || (sira == enIyiSira && maksYuzde > enIyiYuzde))
            {
                enIyi = s;
                enIyiSira = sira;
                enIyiYuzde = maksYuzde;
            }
        }

        if (enIyi is null)
            return null;

        return (enIyi, enIyiYuzde);
    }

    public static string IpucuMetni(KotaVerisi? veri)
    {
        if (veri?.Saglayicilar is null || veri.Saglayicilar.Count == 0)
            return "Kota verisi yok";

        var parcalar = new List<string>();
        foreach (var s in veri.Saglayicilar)
        {
            if (string.IsNullOrEmpty(s.Ad))
                continue;

            if (IpucuHaricSaglayicilar.Contains(s.Ad, StringComparer.OrdinalIgnoreCase))
                continue;

            string ad = SaglayiciAdi(s.Ad);
            if (string.Equals(s.Durum, "hata", StringComparison.OrdinalIgnoreCase))
            {
                parcalar.Add($"{ad} –");
            }
            else
            {
                int yuzde = (int)Math.Round(EnYuksekKullanim(s), MidpointRounding.AwayFromZero);
                parcalar.Add($"{ad} %{yuzde}");
            }
        }

        if (parcalar.Count == 0)
            return "Kota verisi yok";

        string metin = string.Join(" · ", parcalar);
        if (metin.Length > 127)
            return string.Concat(metin.AsSpan(0, 126), "…");

        return metin;
    }

    internal static double EnYuksekKullanim(SaglayiciVerisi saglayici)
    {
        if (saglayici.Pencereler is null || saglayici.Pencereler.Count == 0)
            return 0.0;

        double maks = 0.0;
        foreach (var p in saglayici.Pencereler)
        {
            if (p.Kullanilan > maks)
                maks = p.Kullanilan;
        }
        return maks;
    }
}
