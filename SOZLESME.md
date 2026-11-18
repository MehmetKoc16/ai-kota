# kota — veri sözleşmesi (kota.py yazar, tepsi/KotaTepsi.exe okur)

Veri klasörü: `%LOCALAPPDATA%\kota\` (yoksa oluşturulur). Testlerde `KOTA_DIZIN` ortam değişkeni bu klasörü değiştirir.

## Girdiler (hiçbir gizli giriş belirteci OKUNMAZ, ağ isteği YAPILMAZ)
1. Codex: `~/.codex/sessions/**/*.jsonl` içinde değiştirilme zamanı en yeni dosya; içindeki SON `"rate_limits"` taşıyan satır
   (örnek: `ornek/codex_satir.jsonl`). `payload.rate_limits.primary` (window_minutes=300) ve `.secondary` (10080):
   `used_percent`, `window_minutes`, `resets_at` (epoch saniye). Satırın `timestamp` alanı = veri zamanı.
   Testlerde `KOTA_CODEX_DIZIN` ortam değişkeni `~/.codex/sessions` yerine geçer.
2. agy: `agy.exe -p "/usage" --output-format json` (yol: `%LOCALAPPDATA%\agy\bin\agy.exe`, zaman aşımı 60 sn, stdin kapalı).
   Örnek çıktı: `ornek/agy_usage.json`. `command.data.groups[].buckets[]`: `window` ("5h"|"weekly"), `remaining_fraction`, `reset_time` (ISO).
   Grup adları: "Gemini Models" -> ad "gemini"; "Claude and GPT models" -> "agy-claude-gpt"; "Gemini 4 Argon" -> "argon".
   Sonuç `agy_onbellek.json`'a yazılır; 120 sn'den yeniyse agy yeniden çağrılmaz.
3. Claude: önce Claude Code CLI SDK `get_usage` kontrol isteği kullanılır (Claude Code'un kendi girişi; model çağrısı yok, kota harcamaz; 120 sn önbellek). CLI verisi 10 dakikadan tazeyse doğrudan, değilse diğer kaynaklardan yeni ya da eşitse seçilir. CLI başarısız olursa yerel kaynaklar kullanılır: veri dizinindeki orkestratör `claude.json` (örnek: `ornek/claude_usage.json`) veya `KOTA_CLAUDE_DURUM` / `~/.kota/claude_durum.json` konumundaki statusLine dosyası; ikisi varsa mtime'ı yeni olan geçerlidir. `claude_durum_satiri.py`, Claude Code stdin'indeki `rate_limits` alanını yazar. `five_hour` -> "5s",
   `seven_day` -> "haftalik". `claude.json` etiketleri: "5-hour limit" -> "5s",
   "Weekly · all models" -> "haftalik", "Weekly · <Model>" -> "haftalik-<model küçük harf>". Veri zamanı = dosyanın değiştirilme zamanı.
4. `ayar.json` (isteğe bağlı): `{"sifirlama_hakki": {"codex": true, "claude": true}}`.

## Çıktı: `kota.json`
```json
{
  "olusturma": "2026-11-15T16:20:00+03:00",
  "saglayicilar": [
    {
      "ad": "codex",            // codex | claude | gemini | argon | agy-claude-gpt
      "aile": "codex",          // codex | claude | agy
      "durum": "ok",            // ok | bayat | hata
      "hata": null,             // durum=hata ise kısa Türkçe açıklama
      "veri_zamani": "2026-11-15T16:03:06+03:00",
      "etiket": "dar",          // bol | normal | dar | dolu
      "sifirlama_hakki": true,  // ayar.json'dan; yoksa null
      "pencereler": [
        {
          "ad": "5s",           // 5s | haftalik | haftalik-<model>
          "kullanilan": 48.0,   // 0-100
          "sifirlanma": "2026-11-15T18:10:00+03:00",  // yoksa null
          "pencere_dk": 300,    // yoksa null
          "tempo": {            // pencere_dk ve sifirlanma yoksa null
            "gecen_oran": 0.42,            // pencerenin geçen kısmı 0-1
            "sifirlanmada_tahmin": 114.3,  // bu hızla sıfırlanma anındaki kullanım %; gecen_oran < 0.05 ise null
            "biter": true,                 // sifirlanmada_tahmin >= 100
            "bitis": "2026-11-15T17:40:00+03:00"  // biter ise tahmini %100 anı, değilse null
          }
        }
      ]
    }
  ]
}
```

## Kurallar
- Bayatlık: Codex verisi 30 dk'dan, Claude verisi 60 dk'dan eskiyse `durum: "bayat"` (değerler yine gösterilir).
- `sifirlanma` geçmişteyse pencere sıfırlanmış sayılır: `kullanilan: 0`, `tempo: null`.
- Etiket: pencerelerin en yüksek `kullanilan`'ı < 50 -> bol, < 80 -> normal, < 95 -> dar, aksi -> dolu.
  Herhangi bir pencerede `tempo.biter` true ise etiket en az "dar" olur.
- Bir kaynak okunamazsa o sağlayıcı `durum: "hata"`, `pencereler: []` ile yazılır; diğerleri etkilenmez. Program asla çökmez.
- Tüm zamanlar yerel saat diliminde ISO 8601.
