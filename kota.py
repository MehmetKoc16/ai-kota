"""Codex, Claude ve agy kota kullanım bilgilerini toplayıp kota.json'a yazar."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


AGY_GRUP_ESLEME = {
    "Gemini Models": "gemini",
    "Claude and GPT models": "agy-claude-gpt",
    "Gemini 4 Argon": "argon",
}

AGY_SAGLAYICILAR = ("gemini", "argon", "agy-claude-gpt")


def _simdi_al(simdi: datetime | None = None) -> datetime:
    """Yerel saat dilimine sahip referans zamanı döndürür."""
    if simdi is None:
        return datetime.now().astimezone()
    if simdi.tzinfo is None:
        return simdi.astimezone()
    return simdi


def _iso_coz(metin: str | None, hedef_tz: Any = None) -> datetime | None:
    """ISO 8601 tarih metnini hedef saat diliminde datetime'a çevirir."""
    if not metin or not isinstance(metin, str):
        return None
    s = metin.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if hedef_tz is not None:
        return dt.astimezone(hedef_tz)
    return dt.astimezone()


def _iso_yaz(dt: datetime | None) -> str | None:
    """datetime nesnesini mikrosaniyesiz ISO 8601 metnine çevirir."""
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat()


def veri_dizini() -> Path:
    """KOTA_DIZIN veya %LOCALAPPDATA%\\kota dizinini döndürür, yoksa oluşturur."""
    ortam = os.environ.get("KOTA_DIZIN")
    if ortam:
        dizin = Path(ortam)
    else:
        local_app = os.environ.get("LOCALAPPDATA")
        temel = Path(local_app) if local_app else (Path.home() / "AppData" / "Local")
        dizin = temel / "kota"
    dizin.mkdir(parents=True, exist_ok=True)
    return dizin


def _ayar_oku(dizin: Path) -> dict[str, Any]:
    """İsteğe bağlı ayar.json dosyasını okur; yoksa veya bozuksa boş sözlük döner."""
    ayar_yolu = dizin / "ayar.json"
    if not ayar_yolu.exists():
        return {}
    try:
        veri = json.loads(ayar_yolu.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _sifirlama_hakki_al(ayar: dict[str, Any], ad: str) -> bool | None:
    """ayar.json içinden sağlayıcıya ait sıfırlama hakkı değerini alır."""
    haklar = ayar.get("sifirlama_hakki")
    if isinstance(haklar, dict) and ad in haklar:
        deger = haklar[ad]
        return bool(deger) if deger is not None else None
    return None


def _hata_saglayici(
    ad: str,
    aile: str,
    hata: str,
    sifirlama_hakki: bool | None = None,
) -> dict[str, Any]:
    """Hata durumunda standart sağlayıcı kaydı oluşturur."""
    return {
        "ad": ad,
        "aile": aile,
        "durum": "hata",
        "hata": hata,
        "veri_zamani": None,
        "etiket": None,
        "sifirlama_hakki": sifirlama_hakki,
        "pencereler": [],
    }


def tempo_hesapla(
    kullanilan: float,
    sifirlanma: datetime | str | None,
    pencere_dk: int | None,
    simdi: datetime | None = None,
) -> dict[str, Any] | None:
    """Pencere tüketim hızını ve sıfırlanma öncesi bitiş tahminini hesaplar."""
    if pencere_dk is None or pencere_dk <= 0 or sifirlanma is None:
        return None

    simdi_dt = _simdi_al(simdi)
    if isinstance(sifirlanma, str):
        sifirlanma_dt = _iso_coz(sifirlanma, simdi_dt.tzinfo)
    else:
        sifirlanma_dt = _simdi_al(sifirlanma).astimezone(simdi_dt.tzinfo)

    if sifirlanma_dt is None or sifirlanma_dt <= simdi_dt:
        return None

    pencere_sn = pencere_dk * 60.0
    baslangic = sifirlanma_dt - timedelta(seconds=pencere_sn)
    gecen_sn = (simdi_dt - baslangic).total_seconds()
    if gecen_sn < 0:
        gecen_sn = 0.0
    gecen_oran = min(1.0, gecen_sn / pencere_sn)

    if gecen_oran < 0.05:
        return {
            "gecen_oran": round(gecen_oran, 4),
            "sifirlanmada_tahmin": None,
            "biter": False,
            "bitis": None,
        }

    tahmin_ham = float(kullanilan) / gecen_oran
    tahmin = round(tahmin_ham, 1)
    biter = tahmin >= 100.0
    bitis_iso: str | None = None

    if biter:
        if float(kullanilan) > 0:
            bitis_sn = gecen_sn * (100.0 / float(kullanilan))
            bitis_dt = baslangic + timedelta(seconds=bitis_sn)
        else:
            bitis_dt = simdi_dt
        bitis_iso = _iso_yaz(bitis_dt)

    return {
        "gecen_oran": round(gecen_oran, 4),
        "sifirlanmada_tahmin": tahmin,
        "biter": biter,
        "bitis": bitis_iso,
    }


def etiket_belirle(pencereler: list[dict[str, Any]]) -> str:
    """Pencerelerdeki en yüksek kullanıma ve bitiş durumuna göre etiket döndürür."""
    en_yuksek = max((float(p.get("kullanilan", 0.0)) for p in pencereler), default=0.0)
    if en_yuksek < 50.0:
        etiket = "bol"
    elif en_yuksek < 80.0:
        etiket = "normal"
    elif en_yuksek < 95.0:
        etiket = "dar"
    else:
        etiket = "dolu"

    herhangi_biter = any(
        isinstance(p.get("tempo"), dict) and p["tempo"].get("biter")
        for p in pencereler
    )
    if herhangi_biter and etiket in ("bol", "normal"):
        return "dar"
    return etiket


def _pencere_olustur(
    ad: str,
    kullanilan: float,
    sifirlanma_dt: datetime | None,
    pencere_dk: int | None,
    simdi_dt: datetime,
) -> dict[str, Any]:
    """Sıfırlanma geçmişte ise sıfırlayarak standart pencere sözlüğü oluşturur."""
    if sifirlanma_dt is not None and sifirlanma_dt <= simdi_dt:
        son_kullanilan = 0.0
        tempo = None
    else:
        son_kullanilan = round(float(kullanilan), 1)
        tempo = tempo_hesapla(son_kullanilan, sifirlanma_dt, pencere_dk, simdi_dt)

    return {
        "ad": ad,
        "kullanilan": son_kullanilan,
        "sifirlanma": _iso_yaz(sifirlanma_dt),
        "pencere_dk": pencere_dk,
        "tempo": tempo,
    }


def _sondan_satirlar(dosya_yolu: Path, parca_boyut: int = 8192):
    """Bir metin dosyasını sondan başa doğru satır satır okur."""
    with open(dosya_yolu, "rb") as dosya:
        dosya.seek(0, os.SEEK_END)
        konum = dosya.tell()
        tampon = b""
        while konum > 0:
            okunacak = min(parca_boyut, konum)
            konum -= okunacak
            dosya.seek(konum)
            parca = dosya.read(okunacak)
            tampon = parca + tampon
            satirlar = tampon.split(b"\n")
            tampon = satirlar[0]
            for satir in reversed(satirlar[1:]):
                metin = satir.decode("utf-8", errors="replace").strip()
                if metin:
                    yield metin
        if tampon:
            metin = tampon.decode("utf-8", errors="replace").strip()
            if metin:
                yield metin


def _en_yeni_jsonl_listesi(kok_dizin: Path, adet: int = 10) -> list[Path]:
    """Değiştirilme zamanına göre en yeni JSONL dosyalarını döndürür."""
    if not kok_dizin.exists():
        return []
    dosyalar: list[tuple[float, Path]] = []
    for kok, _, adlar in os.walk(kok_dizin):
        for ad in adlar:
            if not ad.endswith(".jsonl"):
                continue
            yol = Path(kok) / ad
            try:
                mtime = os.path.getmtime(yol)
            except OSError:
                continue
            dosyalar.append((mtime, yol))
    dosyalar.sort(key=lambda kayit: kayit[0], reverse=True)
    return [yol for _, yol in dosyalar[:max(0, adet)]]


def codex_oku(simdi: datetime | None = None) -> dict[str, Any]:
    """Codex oturum dosyalarından son rate_limits kaydını okur."""
    simdi_dt = _simdi_al(simdi)
    ayar = _ayar_oku(veri_dizini())
    hak = _sifirlama_hakki_al(ayar, "codex")

    codex_ortam = os.environ.get("KOTA_CODEX_DIZIN")
    codex_dizini = Path(codex_ortam) if codex_ortam else (Path.home() / ".codex" / "sessions")

    en_yeni_dosyalar = _en_yeni_jsonl_listesi(codex_dizini)
    if not en_yeni_dosyalar:
        return _hata_saglayici("codex", "codex", "Codex oturum dosyası bulunamadı", hak)

    bulunan_satir: dict[str, Any] | None = None
    rate_limits: dict[str, Any] | None = None

    en_yeni = en_yeni_dosyalar[0]
    for dosya in en_yeni_dosyalar:
        for satir in _sondan_satirlar(dosya):
            try:
                veri = json.loads(satir)
            except json.JSONDecodeError:
                continue
            if not isinstance(veri, dict):
                continue
            payload = veri.get("payload")
            if not isinstance(payload, dict):
                continue
            rl = payload.get("rate_limits")
            if isinstance(rl, dict) and ("primary" in rl or "secondary" in rl):
                bulunan_satir = veri
                rate_limits = rl
                en_yeni = dosya
                break
        if bulunan_satir is not None:
            break

    if bulunan_satir is None or rate_limits is None:
        return _hata_saglayici("codex", "codex", "Codex dosyasında rate_limits yok", hak)

    veri_zamani_dt = _iso_coz(bulunan_satir.get("timestamp"), simdi_dt.tzinfo)
    if veri_zamani_dt is None:
        veri_zamani_dt = datetime.fromtimestamp(
            os.path.getmtime(en_yeni), tz=timezone.utc
        ).astimezone(simdi_dt.tzinfo)

    pencereler: list[dict[str, Any]] = []
    for alan, pencere_adi in (("primary", "5s"), ("secondary", "haftalik")):
        kayit = rate_limits.get(alan)
        if not isinstance(kayit, dict) or kayit.get("used_percent") is None:
            continue
        resets_at = kayit.get("resets_at")
        sifirlanma_dt = (
            datetime.fromtimestamp(float(resets_at), tz=timezone.utc).astimezone(simdi_dt.tzinfo)
            if resets_at is not None
            else None
        )
        pencereler.append(
            _pencere_olustur(
                pencere_adi,
                float(kayit["used_percent"]),
                sifirlanma_dt,
                kayit.get("window_minutes"),
                simdi_dt,
            )
        )

    bayat = (simdi_dt - veri_zamani_dt) > timedelta(minutes=30)
    return {
        "ad": "codex",
        "aile": "codex",
        "durum": "bayat" if bayat else "ok",
        "hata": None,
        "veri_zamani": _iso_yaz(veri_zamani_dt),
        "etiket": etiket_belirle(pencereler),
        "sifirlama_hakki": hak,
        "pencereler": pencereler,
    }


def _agy_yolu_bul() -> Path:
    """agy.exe çalıştırılabilir dosya yolunu döndürür."""
    local_app = os.environ.get("LOCALAPPDATA")
    temel = Path(local_app) if local_app else (Path.home() / "AppData" / "Local")
    return temel / "agy" / "bin" / "agy.exe"


def _agy_hata_listesi(ayar: dict[str, Any], hata: str) -> list[dict[str, Any]]:
    """agy kaynaklı tüm sağlayıcılar için hata listesi döndürür."""
    return [
        _hata_saglayici(ad, "agy", hata, _sifirlama_hakki_al(ayar, ad))
        for ad in AGY_SAGLAYICILAR
    ]


def agy_oku(simdi: datetime | None = None, calistir: bool = True) -> list[dict[str, Any]]:
    """agy /usage çıktısını önbellekten veya agy.exe üzerinden okur."""
    simdi_dt = _simdi_al(simdi)
    dizin = veri_dizini()
    ayar = _ayar_oku(dizin)
    onbellek_yolu = dizin / "agy_onbellek.json"

    onbellek_taze = False
    if onbellek_yolu.exists():
        if not calistir:
            onbellek_taze = True
        else:
            try:
                yas = simdi_dt.timestamp() - os.path.getmtime(onbellek_yolu)
                onbellek_taze = yas < 120
            except OSError:
                onbellek_taze = False

    ham_veri: dict[str, Any] | None = None
    veri_zamani_dt = simdi_dt

    if onbellek_taze:
        try:
            ham_veri = json.loads(onbellek_yolu.read_text(encoding="utf-8"))
            veri_zamani_dt = datetime.fromtimestamp(
                os.path.getmtime(onbellek_yolu), tz=timezone.utc
            ).astimezone(simdi_dt.tzinfo)
        except (OSError, json.JSONDecodeError) as exc:
            if not calistir:
                return _agy_hata_listesi(ayar, f"agy önbellek okunamadı: {exc}")
            ham_veri = None

    if ham_veri is None:
        if not calistir:
            return _agy_hata_listesi(ayar, "agy önbellek yok")

        agy_yolu = _agy_yolu_bul()
        if not agy_yolu.exists():
            return _agy_hata_listesi(ayar, "agy.exe bulunamadı")

        calistirma_ayari: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "timeout": 60,
        }
        if sys.platform == "win32":
            calistirma_ayari["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            sonuc = subprocess.run(
                [str(agy_yolu), "-p", "/usage", "--output-format", "json"],
                **calistirma_ayari,
            )
        except subprocess.TimeoutExpired:
            return _agy_hata_listesi(ayar, "agy zaman aşımına uğradı")
        except OSError as exc:
            return _agy_hata_listesi(ayar, f"agy çalıştırılamadı: {exc}")

        if sonuc.returncode != 0:
            return _agy_hata_listesi(ayar, f"agy hata kodu döndü ({sonuc.returncode})")

        try:
            ham_veri = json.loads(sonuc.stdout)
        except json.JSONDecodeError:
            return _agy_hata_listesi(ayar, "agy çıktısı geçersiz JSON")

        try:
            tmp_yol = dizin / "agy_onbellek.json.tmp"
            tmp_yol.write_text(
                json.dumps(ham_veri, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_yol, onbellek_yolu)
        except OSError:
            pass
        veri_zamani_dt = simdi_dt

    gruplar = (
        ham_veri.get("command", {}).get("data", {}).get("groups")
        if isinstance(ham_veri, dict)
        else None
    )
    if not isinstance(gruplar, list):
        return _agy_hata_listesi(ayar, "agy verisinde groups bulunamadı")

    saglayici_haritasi: dict[str, dict[str, Any]] = {}
    for grup in gruplar:
        if not isinstance(grup, dict):
            continue
        ad = AGY_GRUP_ESLEME.get(grup.get("name", ""))
        if not ad:
            continue

        pencereler: list[dict[str, Any]] = []
        for kova in grup.get("buckets", []):
            if not isinstance(kova, dict):
                continue
            kalan = kova.get("remaining_fraction")
            if kalan is None:
                continue
            pencere_turu = kova.get("window")
            if pencere_turu == "5h":
                pencere_adi, pencere_dk = "5s", 300
            elif pencere_turu == "weekly":
                pencere_adi, pencere_dk = "haftalik", 10080
            else:
                pencere_adi, pencere_dk = str(pencere_turu or "diger"), None

            kullanilan = round((1.0 - float(kalan)) * 100.0, 1)
            sifirlanma_dt = _iso_coz(kova.get("reset_time"), simdi_dt.tzinfo)
            pencereler.append(
                _pencere_olustur(pencere_adi, kullanilan, sifirlanma_dt, pencere_dk, simdi_dt)
            )

        saglayici_haritasi[ad] = {
            "ad": ad,
            "aile": "agy",
            "durum": "ok",
            "hata": None,
            "veri_zamani": _iso_yaz(veri_zamani_dt),
            "etiket": etiket_belirle(pencereler),
            "sifirlama_hakki": _sifirlama_hakki_al(ayar, ad),
            "pencereler": pencereler,
        }

    sonuclar: list[dict[str, Any]] = []
    for ad in AGY_SAGLAYICILAR:
        if ad in saglayici_haritasi:
            sonuclar.append(saglayici_haritasi[ad])
        else:
            sonuclar.append(
                _hata_saglayici(
                    ad,
                    "agy",
                    f"agy çıktısında {ad} grubu yok",
                    _sifirlama_hakki_al(ayar, ad),
                )
            )
    return sonuclar


def _claude_pencere_adi_coz(etiket: str) -> tuple[str, int | None]:
    """claude.json pencere etiketini sözleşme adına ve dakika süresine çevirir."""
    if etiket == "5-hour limit":
        return "5s", 300
    if etiket == "Weekly · all models":
        return "haftalik", 10080
    if etiket.startswith("Weekly · "):
        model = etiket[len("Weekly · "):].strip().lower()
        return f"haftalik-{model}", 10080
    return etiket.strip().lower().replace(" ", "-"), None


def _claude_elle_yolu() -> Path:
    """get_usage biçimindeki elle yazılan claude.json yolu (AppData dışında, MSIX yönlendirmesine takılmaz)."""
    return Path(os.environ.get("KOTA_CLAUDE_ELLE") or (Path.home() / ".kota" / "claude.json"))


def _claude_durum_yolu() -> Path:
    """Claude Code statusLine durum dosyasının yolunu döndürür."""
    return Path(os.environ.get("KOTA_CLAUDE_DURUM") or (Path.home() / ".kota" / "claude_durum.json"))


def claude_oku(simdi: datetime | None = None) -> dict[str, Any]:
    """En yeni Claude kaynağını (claude.json veya statusLine) okur."""
    simdi_dt = _simdi_al(simdi)
    dizin = veri_dizini()
    ayar = _ayar_oku(dizin)
    hak = _sifirlama_hakki_al(ayar, "claude")
    claude_yolu = dizin / "claude.json"

    durum_yolu = _claude_durum_yolu()
    adaylar: list[tuple[float, Path, str]] = []
    for yol, tur in ((claude_yolu, "legacy"), (_claude_elle_yolu(), "legacy"), (durum_yolu, "statusline")):
        try:
            adaylar.append((yol.stat().st_mtime, yol, tur))
        except OSError:
            pass
    adaylar.sort(key=lambda a: a[0], reverse=True)
    secilen: tuple[float, Path, str, dict[str, Any]] | None = None
    for mtime, yol, tur in adaylar:
        try:
            veri = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(veri, dict):
            continue
        if tur == "statusline" and not isinstance(veri.get("rate_limits"), dict):
            continue
        secilen = (mtime, yol, tur, veri)
        break
    if secilen is None:
        return _hata_saglayici("claude", "claude", "Claude verisi yok (durum satırı kurulu değil ya da Claude Code çalışmadı)", hak)

    mtime, claude_yolu, kaynak_turu, veri = secilen

    veri_zamani_dt = datetime.fromtimestamp(
        mtime, tz=timezone.utc
    ).astimezone(simdi_dt.tzinfo)

    pencereler: list[dict[str, Any]] = []
    if kaynak_turu == "statusline":
        eslemeler = (("five_hour", "5s", 300), ("seven_day", "haftalik", 10080))
        for alan, ad, dakika in eslemeler:
            pencere = veri["rate_limits"].get(alan)
            if not isinstance(pencere, dict) or pencere.get("used_percentage") is None:
                continue
            reset = pencere.get("resets_at")
            sifirlanma = datetime.fromtimestamp(float(reset), tz=timezone.utc).astimezone(simdi_dt.tzinfo) if reset is not None else None
            pencereler.append(_pencere_olustur(ad, float(pencere["used_percentage"]), sifirlanma, dakika, simdi_dt))
    else:
        for pencere in veri.get("windows", []):
            if not isinstance(pencere, dict):
                continue
            yuzde = pencere.get("percentUsed")
            if yuzde is None:
                continue
            pencere_adi, pencere_dk = _claude_pencere_adi_coz(str(pencere.get("label", "")))
            sifirlanma_dt = _iso_coz(pencere.get("resetsAt"), simdi_dt.tzinfo)
            pencereler.append(
                _pencere_olustur(pencere_adi, float(yuzde), sifirlanma_dt, pencere_dk, simdi_dt)
            )

    bayat = (simdi_dt - veri_zamani_dt) > timedelta(minutes=60)
    return {
        "ad": "claude",
        "aile": "claude",
        "durum": "bayat" if bayat else "ok",
        "hata": None,
        "veri_zamani": _iso_yaz(veri_zamani_dt),
        "etiket": etiket_belirle(pencereler),
        "sifirlama_hakki": hak,
        "pencereler": pencereler,
    }


def topla(simdi: datetime | None = None, agy_calistir: bool = True) -> dict[str, Any]:
    """Tüm sağlayıcılardan kota verilerini güvenli biçimde toplar."""
    simdi_dt = _simdi_al(simdi)
    ayar = _ayar_oku(veri_dizini())
    saglayicilar: list[dict[str, Any]] = []

    try:
        saglayicilar.append(codex_oku(simdi_dt))
    except Exception as exc:
        saglayicilar.append(
            _hata_saglayici("codex", "codex", str(exc), _sifirlama_hakki_al(ayar, "codex"))
        )

    try:
        saglayicilar.append(claude_oku(simdi_dt))
    except Exception as exc:
        saglayicilar.append(
            _hata_saglayici("claude", "claude", str(exc), _sifirlama_hakki_al(ayar, "claude"))
        )

    try:
        saglayicilar.extend(agy_oku(simdi_dt, calistir=agy_calistir))
    except Exception as exc:
        saglayicilar.extend(_agy_hata_listesi(ayar, str(exc)))

    return {
        "olusturma": _iso_yaz(simdi_dt),
        "saglayicilar": saglayicilar,
    }


def yaz(veri: dict[str, Any]) -> Path:
    """Veriyi veri dizinindeki kota.json dosyasına atomik olarak yazar."""
    dizin = veri_dizini()
    hedef = dizin / "kota.json"
    gecici = dizin / "kota.json.tmp"
    icerik = json.dumps(veri, ensure_ascii=False, indent=2)
    gecici.write_text(icerik, encoding="utf-8")
    os.replace(gecici, hedef)
    return hedef


def _sure_bicimle(saniye: float) -> str:
    """Saniye cinsinden süreyi Türkçe kısa biçime çevirir (örn. 2sa 6dk, 4g 1sa)."""
    if saniye <= 0:
        return "0dk"
    toplam = int(saniye)
    gun = toplam // 86400
    saat = (toplam % 86400) // 3600
    dakika = (toplam % 3600) // 60
    if gun > 0:
        return f"{gun}g {saat}sa"
    if saat > 0:
        return f"{saat}sa {dakika}dk"
    return f"{dakika}dk"


def _yuzde_bicimle(deger: float) -> str:
    """Yüzde değerini tam sayı ise ondalıksız, değilse tek ondalıklı biçimler."""
    yuvarli = round(float(deger), 1)
    if yuvarli.is_integer():
        return f"%{int(yuvarli)}"
    return f"%{yuvarli:.1f}"


def _pencere_etiket_tr(ad: str) -> str:
    """Pencere adını tablo çıktısı için Türkçe başlığa çevirir."""
    if ad == "haftalik":
        return "haftalık"
    if ad.startswith("haftalik-"):
        return "haftalık-" + ad[len("haftalik-"):]
    return ad


def tablo_bicimle(veri: dict[str, Any], simdi: datetime | None = None) -> str:
    """Toplanan kota verisini okunabilir Türkçe tablo metnine dönüştürür."""
    simdi_dt = _simdi_al(simdi)
    satirlar: list[str] = []

    for saglayici in veri.get("saglayicilar", []):
        ad = saglayici.get("ad", "?")
        durum = saglayici.get("durum")
        if durum == "hata":
            hata = saglayici.get("hata") or "bilinmeyen hata"
            satirlar.append(f"{ad:<15} hata: {hata}")
            continue

        etiket = saglayici.get("etiket") or "-"
        parcalar = [f"{ad:<15} {etiket:<7}"]

        en_erken_bitis: datetime | None = None
        for pencere in saglayici.get("pencereler", []):
            p_ad = _pencere_etiket_tr(str(pencere.get("ad", "")))
            yuzde = _yuzde_bicimle(float(pencere.get("kullanilan", 0.0)))
            sifirlanma_dt = _iso_coz(pencere.get("sifirlanma"), simdi_dt.tzinfo)
            if sifirlanma_dt is not None:
                kalan_sn = max(0.0, (sifirlanma_dt - simdi_dt).total_seconds())
                parcalar.append(f"{p_ad}:{yuzde} ({_sure_bicimle(kalan_sn)})")
            else:
                parcalar.append(f"{p_ad}:{yuzde}")

            tempo = pencere.get("tempo")
            if isinstance(tempo, dict) and tempo.get("biter") and tempo.get("bitis"):
                bitis_dt = _iso_coz(tempo["bitis"], simdi_dt.tzinfo)
                if bitis_dt is not None and (en_erken_bitis is None or bitis_dt < en_erken_bitis):
                    en_erken_bitis = bitis_dt

        if en_erken_bitis is not None:
            bitis_sn = max(0.0, (en_erken_bitis - simdi_dt).total_seconds())
            parcalar.append(f"! ~{_sure_bicimle(bitis_sn)}'da biter")

        if durum == "bayat":
            parcalar.append("(bayat)")

        satirlar.append(" ".join(parcalar))

    return "\n".join(satirlar)


def main(argv: list[str] | None = None) -> int:
    """Komut satırı giriş noktası."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ayristirici = argparse.ArgumentParser(description="Kota kullanım toplayıcı")
    ayristirici.add_argument("--json", action="store_true", help="JSON çıktısını stdout'a bas")
    ayristirici.add_argument("--yaz", action="store_true", help="Yalnız kota.json'a yaz, çıktı verme")
    ayristirici.add_argument("--claude-dosyasi", metavar="YOL", help="Verilen dosyayı claude.json olarak kopyala")
    arglar = ayristirici.parse_args(argv)

    if arglar.claude_dosyasi:
        hedef_claude = _claude_elle_yolu()
        hedef_claude.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arglar.claude_dosyasi, hedef_claude)

    simdi_dt = _simdi_al()
    veri = topla(simdi=simdi_dt)
    yaz(veri)

    if arglar.yaz:
        return 0
    if arglar.json:
        print(json.dumps(veri, ensure_ascii=False, indent=2))
    else:
        print(tablo_bicimle(veri, simdi=simdi_dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
