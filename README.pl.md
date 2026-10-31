# Borderlands 4 DPS Meter

Licznik DPS w małym okienku w grze. Ma instalator, więc nie trzeba samemu stawiać Python SDK.

[English](README.md)

## Instalacja

1. Pobierz `Borderlands4DpsMeter-Setup-*-PL.msi` z [Releases](../../releases).
2. Zamknij grę i uruchom instalator. Sprawdź wykryty folder gry albo wskaż ten z `Borderlands4.exe`.
3. Uruchom grę. Licznik działa od razu, a menu modów (F7) za pierwszym razem wymaga restartu gry.

Instalator nie jest podpisany, więc SmartScreen może ostrzec. Sumy SHA-256 są w opisie wydania.

Można go mieć razem z [Borderlands 4 Loot Filter](https://github.com/RZADALSON/borderlands-4-loot-filter). Oba korzystają z tego samego SDK, a odinstalowanie jednego zostawia je dla drugiego.

## Co pokazuje

DPS, sumę obrażeń, czas walki, udział krytyków, najlepsze trafienie, zabójstwa i wynik ostatniej walki.

F6 resetuje licznik, F7 otwiera ustawienia.

## Ustawienia

**Liczenie DPS:** cała walka, czyli wszystkie obrażenia podzielone przez czas od pierwszego do ostatniego trafienia, albo tylko ostatnie sekundy (od 1 do 60).

**Reset licznika:** domyślnie licznik zeruje się 5 sekund po ostatnim trafieniu. Można to ustawić od 1 do 60 sekund albo resetować tylko klawiszem F6. Gra nie jest pytana, czy wrogowie są w pobliżu, liczy się tylko to, kiedy kogoś ostatnio trafiłeś.

**Obrażenia w czasie** i **obrażenia towarzyszy** są domyślnie liczone. Każde z nich można wyłączyć.

**Wygląd licznika:** cztery style (domyślnie jak UI gry, kompaktowy, sam tekst i neon), co pokazuje, gdzie stoi i jak jest duży. Gdy menu jest otwarte, licznik się chowa, więc efekt widać po zamknięciu menu.

Ustawienia, które przy Twoim wyborze nic nie zmieniają, są wyszarzone.

**Język:** polski lub angielski, według języka gry w Steamie. Wybór w menu zostaje zapisany. Na Epicu start jest po angielsku.

## Ograniczenia

- Liczy tylko Twoje obrażenia.
- Działa solo i u hosta. Gościom w co-opie gra nie podaje obrażeń, więc licznik zostaje na zerze i mówi dlaczego.

## Odinstalowanie

Ustawienia Windows, Zainstalowane aplikacje, Borderlands 4 DPS Meter.

Jeśli po patchu gra nie chce się uruchomić, odinstaluj licznik albo usuń `OakGame\Binaries\Win64\dsound.dll`.

Autorzy, licencje i budowanie są w [angielskim opisie](README.md).
