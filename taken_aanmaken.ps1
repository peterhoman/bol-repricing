# Maakt de vier dagelijkse taken aan voor de Bol.com NL-automatisering (Tiptopshop).
# Eenmalig uitvoeren: rechtsklik op dit bestand > "Uitvoeren met PowerShell"
# (of vanuit PowerShell: .\taken_aanmaken.ps1)
#
# NL heeft de VROEGE sloten (NL is de belangrijkste winkel, besloten 18/8);
# BE draait op 09:00/10:45/12:15/14:15. Twee scrape-scripts tegelijk geeft
# rate-limiting bij bol.com (~26% mislukte checks), dus de sets staan 45
# minuten verschoven. De sync staat 2 uur na de probe-check vanwege het
# valse-verliezen-effect (Channable moet teruggezette prijzen eerst
# importeren).
#
# VOLGORDE BIJ WIJZIGEN: eerst BE omzetten, dan dit script draaien — anders
# delen beide projecten een dag lang dezelfde sloten.
# Het bestand moet 's ochtends VOOR 08:10 in GitHub staan, anders draait de
# snelstart op de lijst van gisteren.

$py = "C:\Python314\pythonw.exe"   # pythonw: zelfde Python, GEEN zwart venster (dichtklikken doodt de taak)
$base = "C:\Users\Avantius\OneDrive\OneDriveClaude-Code-Projecten\bol-repricing"

if (-not (Test-Path $py)) { Write-Host "FOUT: python niet gevonden op $py"; pause; exit 1 }
if (-not (Test-Path "$base\src\scheduled_run.py")) { Write-Host "FOUT: scheduled_run.py niet gevonden"; pause; exit 1 }

$taken = @(
    @{Naam="Bol NL 1 - ochtend snelstart"; Tijd="08:15"; Arg="morning"},
    @{Naam="Bol NL 2 - probe starten";     Tijd="10:00"; Arg="probe_start"},
    @{Naam="Bol NL 3 - probe controleren"; Tijd="11:30"; Arg="probe_check"},
    @{Naam="Bol NL 4 - sync ronde";        Tijd="13:30"; Arg="sync"}
)

foreach ($t in $taken) {
    $actie = New-ScheduledTaskAction -Execute $py `
        -Argument "`"$base\src\scheduled_run.py`" $($t.Arg)" `
        -WorkingDirectory $base
    $trigger = New-ScheduledTaskTrigger -Daily -At $t.Tijd
    # -WakeToRun: haalt de pc uit de slaapstand voor deze taak
    # -StartWhenAvailable: draait alsnog als het tijdstip gemist werd (pc was uit)
    $instellingen = New-ScheduledTaskSettingsSet -WakeToRun `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName $t.Naam -Action $actie `
        -Trigger $trigger -Settings $instellingen -Force | Out-Null
    Write-Host "Aangemaakt: $($t.Naam)  om $($t.Tijd)"
}

Write-Host ""
Write-Host "Klaar. Controle:"
Get-ScheduledTask -TaskName "Bol NL*" | Select-Object TaskName, State | Format-Table -AutoSize

Write-Host ""
Write-Host "Klaar. De nieuwe tijden gelden vanaf de eerstvolgende dag."
Write-Host "(Geen teststart meer - de taken zijn al bewezen werkend op 17/8.)"
pause
