using System.Text.Json;
using System.Text.Json.Serialization;

namespace KotaTepsi;

public sealed class KotaVerisi
{
    [JsonPropertyName("olusturma")]
    public DateTimeOffset? Olusturma { get; set; }

    [JsonPropertyName("saglayicilar")]
    public List<SaglayiciVerisi>? Saglayicilar { get; set; }

    private static readonly JsonSerializerOptions Secenekler = new()
    {
        AllowTrailingCommas = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
    };

    public static KotaVerisi? Oku(string yol)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(yol) || !File.Exists(yol))
                return null;

            using var akis = new FileStream(
                yol,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            return JsonSerializer.Deserialize<KotaVerisi>(akis, Secenekler);
        }
        catch
        {
            return null;
        }
    }
}

public sealed class SaglayiciVerisi
{
    [JsonPropertyName("ad")]
    public string? Ad { get; set; }

    [JsonPropertyName("aile")]
    public string? Aile { get; set; }

    [JsonPropertyName("durum")]
    public string? Durum { get; set; }

    [JsonPropertyName("hata")]
    public string? Hata { get; set; }

    [JsonPropertyName("veri_zamani")]
    public DateTimeOffset? VeriZamani { get; set; }

    [JsonPropertyName("etiket")]
    public string? Etiket { get; set; }

    [JsonPropertyName("sifirlama_hakki")]
    public bool? SifirlamaHakki { get; set; }

    [JsonPropertyName("pencereler")]
    public List<PencereVerisi>? Pencereler { get; set; }
}

public sealed class PencereVerisi
{
    [JsonPropertyName("ad")]
    public string? Ad { get; set; }

    [JsonPropertyName("kullanilan")]
    public double Kullanilan { get; set; }

    [JsonPropertyName("sifirlanma")]
    public DateTimeOffset? Sifirlanma { get; set; }

    [JsonPropertyName("pencere_dk")]
    public int? PencereDk { get; set; }

    [JsonPropertyName("tempo")]
    public TempoVerisi? Tempo { get; set; }
}

public sealed class TempoVerisi
{
    [JsonPropertyName("gecen_oran")]
    public double? GecenOran { get; set; }

    [JsonPropertyName("sifirlanmada_tahmin")]
    public double? SifirlanmadaTahmin { get; set; }

    [JsonPropertyName("biter")]
    public bool Biter { get; set; }

    [JsonPropertyName("bitis")]
    public DateTimeOffset? Bitis { get; set; }
}
