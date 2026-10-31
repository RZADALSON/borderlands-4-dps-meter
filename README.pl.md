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

**Jak liczyć DPS**

- Cała walka (domyślnie): obrażenia przez czas od pierwszego do ostatniego trafienia.
- Cała walka z przerwami: czas biegnie dalej, więc DPS spada, gdy nie trafiasz.
- Tylko czas trafiania: przerwy dłuższe niż sekunda się nie liczą.
- Ostatnie sekundy: tylko obrażenia z ostatnich 1 do 60 sekund.

**Kiedy resetować**

Domyślnie po 5 sekundach bez trafienia wroga. Można to ustawić od 1 do 60 sekund albo resetować tylko ręcznie. „Poza walką” znaczy tylko tyle, że przez ten czas nikogo nie trafiłeś. Gra nie jest pytana, czy wrogowie są w pobliżu.

**Co się liczy**

Domyślnie pełne obrażenia, takie jak liczby na ekranie, razem z obrażeniami w czasie i od towarzyszy. Każde z tych dwóch można wyłączyć. `Tylko zabrane zdrowie` liczy tylko zdrowie, które wróg naprawdę stracił, więc manekin bez zdrowia liczy się prawie wcale.

**Okienko**

Cztery style: jak UI gry (domyślny), kompaktowy, sam tekst i neon. Można też zmienić miejsce i rozmiar.

**Język**

Polski lub angielski, według języka gry w Steamie. Wybór w menu zostaje zapisany. Na Epicu start jest po angielsku.

## Ograniczenia

- Liczy tylko Twoje obrażenia.
- Działa solo i u hosta. Gościom w co-opie gra nie podaje obrażeń, więc licznik zostaje na zerze i mówi dlaczego.

## Odinstalowanie

Ustawienia Windows, Zainstalowane aplikacje, Borderlands 4 DPS Meter.

Jeśli po patchu gra nie chce się uruchomić, odinstaluj licznik albo usuń `OakGame\Binaries\Win64\dsound.dll`.

Autorzy, licencje i budowanie są w [angielskim opisie](README.md).
