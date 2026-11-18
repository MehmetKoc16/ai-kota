"""kota.py için birim testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import kota
import claude_durum_satiri


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
        self.claude_durum = Path(self.gecici.name) / "claude_durum.json"
        self.kota_dizin.mkdir(parents=True, exist_ok=True)
        self.codex_dizin.mkdir(parents=True, exist_ok=True)
        self.ortam_yama = patch.dict(
            os.environ,
            {
                "KOTA_DIZIN": str(self.kota_dizin),
                "KOTA_CODEX_DIZIN": str(self.codex_dizin),
                "KOTA_CLAUDE_DURUM": str(self.claude_durum),
                "KOTA_CLAUDE_ELLE": str(Path(self.gecici.name) / "kota_ev" / "claude.json"),
                "LOCALAPPDATA": self.gecici.name,
                "APPDATA": self.gecici.name,
            },
        )
        self.ortam_yama.start()
        self.cli_yama = patch.object(kota, "_claude_exe_bul", return_value=None)
        self.cli_yama.start()

    def tearDown(self) -> None:
        self.cli_yama.stop()
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

    def test_codex_en_yeni_dosyada_rate_limits_yok(self) -> None:
        """NEDEN: En yeni oturum boşken önceki oturumdaki kota kaydının kullanılmasını doğrular."""
        eski = self.codex_dizin / "eski.jsonl"
        yeni = self.codex_dizin / "yeni.jsonl"
        eski.write_text(ORNEK_CODEX_SATIR + "\n", encoding="utf-8")
        yeni.write_text('{"payload":{}}\n', encoding="utf-8")
        os.utime(eski, (SIMDI.timestamp() - 20, SIMDI.timestamp() - 20))
        os.utime(yeni, (SIMDI.timestamp(), SIMDI.timestamp()))
        sonuc = kota.codex_oku(simdi=SIMDI)
        self.assertEqual(sonuc["durum"], "ok")
        self.assertEqual([p["kullanilan"] for p in sonuc["pencereler"]], [48.0, 82.0])

    def test_codex_hicbir_dosyada_rate_limits_yok(self) -> None:
        """NEDEN: Rate limit içermeyen tüm oturumlarda mevcut hata metninin korunduğunu doğrular."""
        (self.codex_dizin / "oturum.jsonl").write_text('{"payload":{}}\n', encoding="utf-8")
        sonuc = kota.codex_oku(simdi=SIMDI)
        self.assertEqual(sonuc["hata"], "Codex dosyasında rate_limits yok")

    def test_claude_durum_satiri_okuma(self) -> None:
        """NEDEN: StatusLine yüzdelerinin, pencere adlarının ve reset zamanlarının çevrimini doğrular."""
        veri = {"rate_limits": {"five_hour": {"used_percentage": 5, "resets_at": 1794772800}, "seven_day": {"used_percentage": 1, "resets_at": 1795100400}}}
        self.claude_durum.write_text(json.dumps(veri), encoding="utf-8")
        os.utime(self.claude_durum, (SIMDI.timestamp(), SIMDI.timestamp()))
        sonuc = kota.claude_oku(simdi=SIMDI)
        self.assertEqual([p["ad"] for p in sonuc["pencereler"]], ["5s", "haftalik"])
        self.assertEqual([p["kullanilan"] for p in sonuc["pencereler"]], [5.0, 1.0])
        self.assertEqual(sonuc["pencereler"][0]["sifirlanma"], datetime.fromtimestamp(1794772800, timezone.utc).astimezone(TZ_TR).isoformat())

    def test_claude_daha_yeni_kaynak_secilir(self) -> None:
        """NEDEN: İki Claude girdisinde mtime'ı yeni olan kaynağın her iki yönde seçildiğini doğrular."""
        legacy = self.kota_dizin / "claude.json"
        legacy.write_text(json.dumps({"windows": [{"label": "5-hour limit", "percentUsed": 22, "resetsAt": "2026-11-15T18:00:00+03:00"}]}), encoding="utf-8")
        self.claude_durum.write_text(json.dumps({"rate_limits": {"five_hour": {"used_percentage": 5}}}), encoding="utf-8")
        os.utime(legacy, (SIMDI.timestamp(), SIMDI.timestamp()))
        os.utime(self.claude_durum, (SIMDI.timestamp() + 10, SIMDI.timestamp() + 10))
        self.assertEqual(kota.claude_oku(SIMDI)["pencereler"][0]["kullanilan"], 5.0)
        os.utime(legacy, (SIMDI.timestamp() + 20, SIMDI.timestamp() + 20))
        self.assertEqual(kota.claude_oku(SIMDI)["pencereler"][0]["kullanilan"], 22.0)

    def test_claude_masaustu_olcum_zamani(self) -> None:
        yol = Path(self.gecici.name) / "Claude-Data/claude_test/plan-usage-history.json"
        yol.parent.mkdir(parents=True)
        zaman = int(SIMDI.timestamp() * 1000)
        yol.write_text(json.dumps({"samples": [
            {"t": zaman, "u": {"fh": 100, "sd": 14}},
            {"t": zaman - 1000, "u": {"fh": 67}},
        ]}), encoding="utf-8")
        sonuc = kota.claude_oku(SIMDI)
        self.assertEqual(sonuc["etiket"], "dolu")
        self.assertEqual([p["kullanilan"] for p in sonuc["pencereler"]], [100, 14])
        self.assertEqual(sonuc["veri_zamani"], kota._iso_yaz(SIMDI))
        self.claude_durum.write_text(json.dumps({"rate_limits": {"five_hour": {"used_percentage": 2}}}))
        os.utime(self.claude_durum, (SIMDI.timestamp() + 1,) * 2)
        self.assertEqual(kota.claude_oku(SIMDI)["pencereler"][0]["kullanilan"], 2)

    def test_masaustu_yuzdesi_sifirlanmayi_gecmez(self) -> None:
        yol = Path(self.gecici.name) / "Claude/plan-usage-history.json"
        yol.parent.mkdir()
        reset = SIMDI.timestamp()
        def masaustu_yaz(zaman, yuzde):
            yol.write_text(json.dumps({"samples": [
                {"t": int(zaman * 1000), "u": {"fh": yuzde, "sd": 14}}
            ]}))
        legacy = self.kota_dizin / "claude.json"
        legacy.write_text(json.dumps({"windows": [
            {"label": "5-hour limit", "resetsAt": SIMDI.isoformat(), "percentUsed": 67}
        ]}))
        os.utime(legacy, (reset - 600,) * 2)
        masaustu_yaz(reset - 120, 100)
        self.assertEqual(kota.claude_oku(SIMDI - timedelta(seconds=1))["etiket"], "dolu")
        self.assertEqual([p["kullanilan"] for p in kota.claude_oku(SIMDI)["pencereler"]], [0, 14])
        masaustu_yaz(reset + 1, 52)
        sonuc = kota.claude_oku(SIMDI + timedelta(seconds=2))
        self.assertEqual(sonuc["pencereler"][0]["kullanilan"], 52)
        self.assertIsNone(sonuc["pencereler"][0]["sifirlanma"])

    def test_claude_veri_yok(self) -> None:
        """NEDEN: İki Claude kaynağı da yokken yeni hata açıklamasının verildiğini doğrular."""
        sonuc = kota.claude_oku(SIMDI)
        self.assertEqual(sonuc["hata"], "Claude verisi yok (durum satırı kurulu değil ya da Claude Code çalışmadı)")

    def test_durum_satiri_betigi_yazar(self) -> None:
        """NEDEN: Betiğin bayt stdin'i dosyaya atomik yazıp tek satırlık özet verdiğini doğrular."""
        veri = {"rate_limits": {"five_hour": {"used_percentage": 5}, "seven_day": {"used_percentage": 1}}}
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(veri).encode("utf-8")), encoding="utf-8")
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            self.assertEqual(claude_durum_satiri.main(), 0)
        self.assertTrue(self.claude_durum.exists())
        self.assertEqual(stdout.getvalue().strip(), "Claude 5s %5 · hafta %1")

    def test_durum_satiri_rate_limits_yok(self) -> None:
        """NEDEN: Eksik rate_limits ve bozuk JSON için dosya yazılmadığını ve hatanın dışarı taşmadığını doğrular."""
        for icerik in (b'{"spend_limit":1}', b'{bozuk'):
            stdin = io.TextIOWrapper(io.BytesIO(icerik), encoding="utf-8")
            with patch("sys.stdin", stdin), patch("sys.stdout", io.StringIO()):
                self.assertEqual(claude_durum_satiri.main(), 0)
            self.assertFalse(self.claude_durum.exists())

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

    def _cli_kotalari(self):
        return {"rate_limits_available": True, "rate_limits": {
            "five_hour": {"utilization": 21, "resets_at": "2026-11-18T11:00:00.355219+00:00"},
            "seven_day": {"utilization": 39, "resets_at": "2026-11-19T15:00:00.355238+00:00"},
        }}

    def test_claude_cli_birincil_kaynak(self) -> None:
        """NEDEN: Daha yeni CLI kullanım yanıtının eski claude.json kaynağını geçtiğini doğrular."""
        eski = self.kota_dizin / "claude.json"
        eski.write_text(json.dumps({"windows": [
            {"label": "5-hour limit", "percentUsed": 5},
            {"label": "Weekly · all models", "percentUsed": 1},
        ]}), encoding="utf-8")
        os.utime(eski, (SIMDI.timestamp() - 60,)*2)
        with patch.object(kota, "_claude_exe_bul", return_value=Path("claude.exe")), patch.object(kota, "_claude_cli_istek", return_value=self._cli_kotalari()):
            sonuc = kota.claude_oku(SIMDI)
        self.assertEqual([p["kullanilan"] for p in sonuc["pencereler"]], [21, 39])
        self.assertTrue(all(p["sifirlanma"] for p in sonuc["pencereler"]))
        self.assertEqual(sonuc["durum"], "ok")

    def test_claude_cli_onbellek_120_sn(self) -> None:
        """NEDEN: 120 saniyelik CLI önbelleğinin ikinci çağrıda tekrar istek yapmadığını doğrular."""
        with patch.object(kota, "_claude_exe_bul", return_value=Path("claude.exe")), patch.object(kota, "_claude_cli_istek", return_value=self._cli_kotalari()) as istek:
            kota.claude_cli_oku(SIMDI)
            kota.claude_cli_oku(SIMDI + timedelta(seconds=60))
        istek.assert_called_once()

    def test_claude_cli_hata_eski_kaynaga_duser(self) -> None:
        """NEDEN: CLI hatası ve önbellek yokluğunda claude.json okumaya devam edildiğini doğrular."""
        yol = self.kota_dizin / "claude.json"
        yol.write_text(json.dumps(ORNEK_CLAUDE_JSON), encoding="utf-8")
        os.utime(yol, (SIMDI.timestamp(),)*2)
        with patch.object(kota, "_claude_exe_bul", return_value=Path("claude.exe")), patch.object(kota, "_claude_cli_istek", side_effect=RuntimeError("hata")):
            sonuc = kota.claude_oku(SIMDI)
        self.assertEqual(sonuc["durum"], "ok")
        self.assertEqual(sonuc["pencereler"][0]["kullanilan"], 33)

    def test_claude_cli_calistir_false(self) -> None:
        """NEDEN: calistir=False iken CLI isteğinin başlatılmadığını doğrular."""
        with patch.object(kota, "_claude_cli_istek") as istek:
            self.assertIsNone(kota.claude_cli_oku(SIMDI, calistir=False))
        istek.assert_not_called()

    def test_claude_cli_istek_protokolu(self) -> None:
        """NEDEN: SDK initialize/get_usage isteklerinin iki satır olarak yazılıp yanıtın çözüldüğünü doğrular."""
        class SahteStdin(io.BytesIO):
            def close(self):
                self.deger = self.getvalue()
        class SahtePopen:
            son_ornek = None
            def __init__(self, *args, **kwargs):
                SahtePopen.son_ornek = self
                self.stdin = SahteStdin()
                self.stdout = io.BytesIO(b'{"type":"control_response","response":{"request_id":"kota-init"}}\n' + json.dumps({"type":"control_response", "response":{"subtype":"success", "request_id":"kota-usage", "response":self_outer._cli_kotalari()}}).encode() + b"\n")
                self.returncode = None
            def wait(self, timeout=None): self.returncode = 0; return 0
            def poll(self): return self.returncode
            def kill(self): self.returncode = -9
        self_outer = self
        with patch.object(kota.subprocess, "Popen", SahtePopen):
            sonuc = kota._claude_cli_istek(Path("claude.exe"))
        self.assertEqual(sonuc, self._cli_kotalari())
        self.assertEqual(len(SahtePopen.son_ornek.stdin.deger.splitlines()), 2)

    def test_claude_cli_null_ve_bilinmeyen_atlanir(self) -> None:
        """NEDEN: Null opus ve tanınmayan cinder_cove pencerelerinin sonuca eklenmediğini doğrular."""
        rate_limits = self._cli_kotalari()["rate_limits"]
        rate_limits["seven_day_opus"] = None
        rate_limits["cinder_cove"] = {"utilization": 99}
        with patch.object(kota, "_claude_exe_bul", return_value=Path("claude.exe")), patch.object(kota, "_claude_cli_istek", return_value={"rate_limits_available": True, "rate_limits": rate_limits}):
            sonuc = kota.claude_oku(SIMDI)
        self.assertEqual([p["ad"] for p in sonuc["pencereler"]], ["5s", "haftalik"])

    def test_claude_ev_dizinindeki_elle_dosya_okunur(self) -> None:
        """NEDEN: Claude masaüstü (MSIX) AppData yazımlarını yönlendirdiği için get_usage verisi ~/.kota/claude.json'dan da okunmalı."""
        elle = Path(os.environ["KOTA_CLAUDE_ELLE"])
        elle.parent.mkdir(parents=True, exist_ok=True)
        elle.write_text(json.dumps(ORNEK_CLAUDE_JSON), encoding="utf-8")
        os.utime(elle, (SIMDI.timestamp(), SIMDI.timestamp()))
        sonuc = kota.claude_oku(simdi=SIMDI)
        self.assertEqual(sonuc["durum"], "ok")
        self.assertEqual([p["ad"] for p in sonuc["pencereler"]], ["5s", "haftalik", "haftalik-fable"])

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
