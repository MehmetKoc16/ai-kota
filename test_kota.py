"""kota.py için birim testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import kota


TZ_TR = timezone(timedelta(hours=3))
SIMDI = datetime(2026, 11, 15, 16, 12, 0, tzinfo=TZ_TR)

ORNEK_CODEX_SATIR = json.dumps(
    {
        "timestamp": "2026-11-15T13:03:06.529Z",
        "ordinal": 58,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "rate_limits": {
                "limit_id": "codex",
                "limit_name": None,
                "primary": {
                    "used_percent": 48.0,
                    "window_minutes": 300,
                    "resets_at": 1794754799,
                },
                "secondary": {
                    "used_percent": 82.0,
                    "window_minutes": 10080,
                    "resets_at": 1795010649,
                },
            },
        },
    }
)

ORNEK_AGY_JSON = {
    "conversation_id": "",
    "status": "SUCCESS",
    "command": {
        "name": "usage",
        "data": {
            "groups": [
                {
                    "name": "Gemini Models",
                    "buckets": [
                        {
                            "id": "gemini-weekly",
                            "window": "weekly",
                            "remaining_fraction": 0.967426061630249,
                            "reset_time": "2026-11-22T12:11:02Z",
                        },
                        {
                            "id": "gemini-5h",
                            "window": "5h",
                            "remaining_fraction": 0.9609912037849426,
                            "reset_time": "2026-11-15T17:11:02Z",
                        },
                    ],
                },
                {
                    "name": "Claude and GPT models",
                    "buckets": [
                        {
                            "id": "3p-weekly",
                            "window": "weekly",
                            "remaining_fraction": 1,
                            "reset_time": "2026-11-22T12:53:23Z",
                        },
                        {
                            "id": "3p-5h",
                            "window": "5h",
                            "remaining_fraction": 1,
                            "reset_time": "2026-11-15T17:53:23Z",
                        },
                    ],
                },
                {
                    "name": "Gemini 4 Argon",
                    "buckets": [
                        {
                            "id": "gemini-argon-wtu-weekly",
                            "window": "weekly",
                            "remaining_fraction": 0.9898666739463806,
                            "reset_time": "2026-11-22T12:48:51Z",
                        }
                    ],
                },
            ]
        },
    },
}

ORNEK_CLAUDE_JSON = {
    "status": "ok",
    "plan": "Pro",
    "windows": [
        {
            "label": "5-hour limit",
            "percentUsed": 33,
            "resetsAt": "2026-11-15T15:10:00.349Z",
            "resetsIn": "2h 6m",
        },
        {
            "label": "Weekly · all models",
            "percentUsed": 80,
            "resetsAt": "2026-11-19T15:00:00.349Z",
            "resetsIn": "4d 1h",
        },
        {
            "label": "Weekly · Fable",
            "percentUsed": 88,
            "resetsAt": "2026-11-19T15:00:00.349Z",
            "resetsIn": "4d 1h",
        },
    ],
}


class TestKota(unittest.TestCase):
    """kota.py fonksiyonları için yalıtılmış geçici dizin testleri."""

    def setUp(self) -> None:
        self.gecici = tempfile.TemporaryDirectory()
        self.kota_dizin = Path(self.gecici.name) / "kota_veri"
        self.codex_dizin = Path(self.gecici.name) / "codex_oturum"
        self.kota_dizin.mkdir(parents=True, exist_ok=True)
        self.codex_dizin.mkdir(parents=True, exist_ok=True)
        self.ortam_yama = patch.dict(
            os.environ,
            {
                "KOTA_DIZIN": str(self.kota_dizin),
                "KOTA_CODEX_DIZIN": str(self.codex_dizin),
            },
        )
        self.ortam_yama.start()

    def tearDown(self) -> None:
        self.ortam_yama.stop()
        self.gecici.cleanup()

    def test_codex_ornek_okuma(self) -> None:
        """NEDEN: Codex oturum jsonl satırından 5s/haftalık yüzdeleri ve bozuk satır atlamayı doğrular."""
        alt_dizin = self.codex_dizin / "2026" / "11"
        alt_dizin.mkdir(parents=True, exist_ok=True)
        oturum = alt_dizin / "rollout.jsonl"
        oturum.write_text(
            '{"type":"other"}\n' + ORNEK_CODEX_SATIR + "\n{bozuk json satiri\n",
            encoding="utf-8",
        )

        sonuc = kota.codex_oku(simdi=SIMDI)
        self.assertEqual(sonuc["ad"], "codex")
        self.assertEqual(sonuc["durum"], "ok")
        self.assertEqual(len(sonuc["pencereler"]), 2)
        p5, ph = sonuc["pencereler"]
        self.assertEqual(p5["ad"], "5s")
        self.assertEqual(p5["kullanilan"], 48.0)
        self.assertEqual(p5["pencere_dk"], 300)
        self.assertEqual(ph["ad"], "haftalik")
        self.assertEqual(ph["kullanilan"], 82.0)
        self.assertEqual(ph["pencere_dk"], 10080)

    def test_codex_dosyasi_yok(self) -> None:
        """NEDEN: Codex oturum dosyası olmadığında çökmeden durum='hata' döndüğünü doğrular."""
        sonuc = kota.codex_oku(simdi=SIMDI)
        self.assertEqual(sonuc["ad"], "codex")
        self.assertEqual(sonuc["durum"], "hata")
        self.assertEqual(sonuc["pencereler"], [])
        self.assertTrue(sonuc["hata"])

    def test_agy_ornek_okuma(self) -> None:
        """NEDEN: agy önbelleğinden gemini, argon ve agy-claude-gpt yüzdelerinin 1 ondalıkla hesaplandığını doğrular."""
        onbellek = self.kota_dizin / "agy_onbellek.json"
        onbellek.write_text(json.dumps(ORNEK_AGY_JSON), encoding="utf-8")

        sonuclar = kota.agy_oku(simdi=SIMDI, calistir=False)
        harita = {s["ad"]: s for s in sonuclar}
        self.assertEqual(set(harita.keys()), {"gemini", "argon", "agy-claude-gpt"})

        gemini_p = {p["ad"]: p for p in harita["gemini"]["pencereler"]}
        self.assertEqual(gemini_p["5s"]["kullanilan"], 3.9)
        self.assertEqual(gemini_p["haftalik"]["kullanilan"], 3.3)

        argon_p = {p["ad"]: p for p in harita["argon"]["pencereler"]}
        self.assertEqual(argon_p["haftalik"]["kullanilan"], 1.0)

        claude_gpt_p = {p["ad"]: p for p in harita["agy-claude-gpt"]["pencereler"]}
        self.assertEqual(claude_gpt_p["5s"]["kullanilan"], 0.0)
        self.assertEqual(claude_gpt_p["haftalik"]["kullanilan"], 0.0)

    def test_claude_ornek_okuma(self) -> None:
        """NEDEN: claude.json etiketlerinin 5s, haftalik ve haftalik-fable olarak dönüştüğünü doğrular."""
        claude_yolu = self.kota_dizin / "claude.json"
        claude_yolu.write_text(json.dumps(ORNEK_CLAUDE_JSON), encoding="utf-8")
        os.utime(claude_yolu, (SIMDI.timestamp(), SIMDI.timestamp()))

        sonuc = kota.claude_oku(simdi=SIMDI)
        self.assertEqual(sonuc["ad"], "claude")
        self.assertEqual(sonuc["durum"], "ok")
        adlar = [p["ad"] for p in sonuc["pencereler"]]
        self.assertEqual(adlar, ["5s", "haftalik", "haftalik-fable"])

    def test_sifirlanma_gecmiste(self) -> None:
        """NEDEN: Sıfırlanma zamanı geçmişte kalan pencerenin kullanilan=0 ve tempo=None olduğunu doğrular."""
        veri = {
            "status": "ok",
            "windows": [
                {
                    "label": "5-hour limit",
                    "percentUsed": 75,
                    "resetsAt": "2026-11-15T12:00:00Z",
                }
            ],
        }
        claude_yolu = self.kota_dizin / "claude.json"
        claude_yolu.write_text(json.dumps(veri), encoding="utf-8")
        os.utime(claude_yolu, (SIMDI.timestamp(), SIMDI.timestamp()))

        sonuc = kota.claude_oku(simdi=SIMDI)
        pencere = sonuc["pencereler"][0]
        self.assertEqual(pencere["kullanilan"], 0.0)
        self.assertIsNone(pencere["tempo"])

    def test_tempo_biter(self) -> None:
        """NEDEN: Pencere %50 geçmiş ve kullanım %60 iken tahmin=120, biter=True ve bitis anını doğrular."""
        ref = datetime(2026, 11, 15, 15, 0, 0, tzinfo=TZ_TR)
        sifirlanma = datetime(2026, 11, 15, 17, 30, 0, tzinfo=TZ_TR)
        tempo = kota.tempo_hesapla(60.0, sifirlanma, 300, simdi=ref)

        self.assertIsNotNone(tempo)
        self.assertEqual(tempo["gecen_oran"], 0.5)
        self.assertEqual(tempo["sifirlanmada_tahmin"], 120.0)
        self.assertTrue(tempo["biter"])
        self.assertEqual(tempo["bitis"], "2026-11-15T16:40:00+03:00")

    def test_tempo_dusuk_gecen_oran(self) -> None:
        """NEDEN: Pencerenin %5'inden azı geçmişken sifirlanmada_tahmin değerinin None olduğunu doğrular."""
        ref = datetime(2026, 11, 15, 15, 0, 0, tzinfo=TZ_TR)
        sifirlanma = ref + timedelta(minutes=290)
        tempo = kota.tempo_hesapla(20.0, sifirlanma, 300, simdi=ref)

        self.assertIsNotNone(tempo)
        self.assertLess(tempo["gecen_oran"], 0.05)
        self.assertIsNone(tempo["sifirlanmada_tahmin"])
        self.assertFalse(tempo["biter"])

    def test_etiket_esikleri_ve_biter(self) -> None:
        """NEDEN: Etiket eşiklerini (49.9/50/79.9/80/94.9/95) ve biter=True durumunda en az 'dar' kuralını doğrular."""
        beklenenler = [
            (49.9, "bol"),
            (50.0, "normal"),
            (79.9, "normal"),
            (80.0, "dar"),
            (94.9, "dar"),
            (95.0, "dolu"),
        ]
        for yuzde, beklenen in beklenenler:
            self.assertEqual(
                kota.etiket_belirle([{"kullanilan": yuzde, "tempo": None}]),
                beklenen,
            )

        self.assertEqual(
            kota.etiket_belirle([{"kullanilan": 10.0, "tempo": {"biter": True}}]),
            "dar",
        )
        self.assertEqual(
            kota.etiket_belirle([{"kullanilan": 96.0, "tempo": {"biter": True}}]),
            "dolu",
        )

    def test_codex_bayatlik(self) -> None:
        """NEDEN: 31 dakika eski Codex verisinin durum='bayat' olarak işaretlendiğini doğrular."""
        oturum = self.codex_dizin / "rollout.jsonl"
        oturum.write_text(ORNEK_CODEX_SATIR + "\n", encoding="utf-8")

        otuz_bir_dk_sonra = datetime(2026, 11, 15, 16, 34, 7, tzinfo=TZ_TR)
        sonuc = kota.codex_oku(simdi=otuz_bir_dk_sonra)
        self.assertEqual(sonuc["durum"], "bayat")
        self.assertEqual(len(sonuc["pencereler"]), 2)

    def test_yaz_atomik(self) -> None:
        """NEDEN: yaz() fonksiyonunun geçici dosya bırakmadan geçerli kota.json yazdığını doğrular."""
        ornek_veri = {"olusturma": "2026-11-15T16:12:00+03:00", "saglayicilar": []}
        hedef = kota.yaz(ornek_veri)

        self.assertTrue(hedef.exists())
        self.assertFalse((self.kota_dizin / "kota.json.tmp").exists())
        okunan = json.loads(hedef.read_text(encoding="utf-8"))
        self.assertEqual(okunan, ornek_veri)


if __name__ == "__main__":
    unittest.main()
