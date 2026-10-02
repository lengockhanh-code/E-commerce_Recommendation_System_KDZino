$ErrorActionPreference = 'Stop'
$slideDir = 'D:\MerRec\report\merrec_canva'
$pptxFile = Join-Path $slideDir 'MERREC_THUYET_TRINH_40_SLIDE.pptx'
$pdfFile = Join-Path $slideDir 'MERREC_THUYET_TRINH_40_SLIDE.pdf'
$renderDir = Join-Path $slideDir 'powerpoint_preview'
New-Item -ItemType Directory -Path $renderDir -Force | Out-Null
$pptApplication = $null
$pptDocument = $null
$previousCount = -1
$previousAlerts = $null
try {
    $pptApplication = New-Object -ComObject PowerPoint.Application
    $previousCount = $pptApplication.Presentations.Count
    $previousAlerts = $pptApplication.DisplayAlerts
    $pptApplication.DisplayAlerts = 1
    $pptDocument = $pptApplication.Presentations.Open($pptxFile, -1, 0, 0)
    $pptDocument.SaveAs($pdfFile, 32)
    $pptDocument.Export($renderDir, 'PNG', 1600, 900)
    $overflow = @()
    foreach ($slide in $pptDocument.Slides) {
        foreach ($shape in $slide.Shapes) {
            if ($shape.HasTable -eq -1) {
                for ($ri = 1; $ri -le $shape.Table.Rows.Count; $ri++) {
                    for ($ci = 1; $ci -le $shape.Table.Columns.Count; $ci++) {
                        $cellShape = $shape.Table.Cell($ri, $ci).Shape
                        $cellTf = $cellShape.TextFrame
                        $cellAvailable = $cellShape.Height - $cellTf.MarginTop - $cellTf.MarginBottom
                        $cellActual = $cellTf.TextRange.BoundHeight
                        if ($cellActual -gt ($cellAvailable + 2)) {
                            $overflow += [PSCustomObject]@{slide=$slide.SlideIndex;shape="Table cell $ri,$ci";available=$cellAvailable;actual=$cellActual;text=$cellTf.TextRange.Text}
                        }
                    }
                }
            }
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
                $tf = $shape.TextFrame
                $available = $shape.Height - $tf.MarginTop - $tf.MarginBottom
                $actual = $tf.TextRange.BoundHeight
                if ($actual -gt ($available + 2)) {
                    $overflow += [PSCustomObject]@{slide=$slide.SlideIndex;shape=$shape.Name;available=$available;actual=$actual;text=$tf.TextRange.Text}
                }
            }
        }
    }
    ConvertTo-Json -InputObject @($overflow) -Depth 4 | Set-Content -LiteralPath (Join-Path $slideDir 'POWERPOINT_TEXT_OVERFLOW.json') -Encoding UTF8
    [PSCustomObject]@{slides=$pptDocument.Slides.Count;overflowCount=$overflow.Count;pdf=$pdfFile;preview=$renderDir} | ConvertTo-Json -Compress
} finally {
    if ($null -ne $pptDocument) {
        $pptDocument.Close()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($pptDocument)
    }
    if ($null -ne $pptApplication) {
        if ($null -ne $previousAlerts) {$pptApplication.DisplayAlerts = $previousAlerts}
        if ($previousCount -eq 0 -and $pptApplication.Presentations.Count -eq 0) {$pptApplication.Quit()}
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($pptApplication)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

