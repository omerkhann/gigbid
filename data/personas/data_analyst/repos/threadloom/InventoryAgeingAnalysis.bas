Attribute VB_Name = "InventoryAgeingAnalysis"
Option Explicit

' This module performs inventory ageing analysis and generates a markdown plan

Private Const AGE_THRESHOLD As Integer = 90 ' days
Private Const MARKDOWN_RATE As Double = 0.70

' Entry point
Public Sub RunAnalysis()
    Dim wsSrc As Worksheet
    Dim wsReport As Worksheet
    Dim lastRow As Long
    Dim i As Long
    Dim totalValue As Double
    Dim slowStockValue As Double
    Dim pctSlow As Double

    Set wsSrc = ThisWorkbook.Worksheets("InventoryData")
    On Error Resume Next
    Set wsReport = ThisWorkbook.Worksheets("AgeingReport")
    If wsReport Is Nothing Then
        Set wsReport = ThisWorkbook.Worksheets.Add(After:=wsSrc)
        wsReport.Name = "AgeingReport"
    End If
    On Error GoTo 0

    lastRow = wsSrc.Cells(wsSrc.Rows.Count, "A").End(xlUp).Row

    ' Clear previous report
    wsReport.Cells.Clear
    wsReport.Range("A1:D1").Value = Array("SKU", "DaysInStock", "Value", "AgeingFlag")
    wsReport.Range("A1:D1").Font.Bold = True

    totalValue = 0
    slowStockValue = 0

    For i = 2 To lastRow
        Dim sku As String
        Dim daysInStock As Long
        Dim value As Double
        Dim flag As String

        sku = wsSrc.Cells(i, "A").Value
        daysInStock = wsSrc.Cells(i, "B").Value
        value = wsSrc.Cells(i, "C").Value

        flag = IIf(daysInStock >= AGE_THRESHOLD, "Slow", "Normal")

        wsReport.Cells(i, "A").Value = sku
        wsReport.Cells(i, "B").Value = daysInStock
        wsReport.Cells(i, "C").Value = value
        wsReport.Cells(i, "D").Value = flag

        totalValue = totalValue + value
        If flag = "Slow" Then slowStockValue = slowStockValue + value
    Next i

    pctSlow = IIf(totalValue = 0, 0, slowStockValue / totalValue)
    wsReport.Range("F2").Value = "Total Value"
    wsReport.Range("G2").Value = totalValue
    wsReport.Range("F3").Value = "Slow Stock Value"
    wsReport.Range("G3").Value = slowStockValue
    wsReport.Range("F4").Value = "% Slow Stock"
    wsReport.Range("G4").Value = pctSlow

    ' Generate markdown plan for slow items
    Dim mdFile As String
    mdFile = ThisWorkbook.Path & "\MarkdownPlan.md"
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim txt As Object
    Set txt = fso.CreateTextFile(mdFile, True)
    txt.WriteLine "# Markdown Plan"
    txt.WriteLine "" & vbCrLf & "## Slow Stock Summary"
    txt.WriteLine "- Total slow stock value: $" & Format(slowStockValue, "#,##0")
    txt.WriteLine "- Markdown target: " & Format(MARKDOWN_RATE * 100, "0.0") & "%"
    txt.WriteLine "- Expected savings: $" & Format(MARKDOWN_RATE * slowStockValue, "#,##0")

    txt.WriteLine vbCrLf & "## SKU Breakdown"
    txt.WriteLine "| SKU | Days In Stock | Value |" & vbCrLf & "|-----|---------------|-------|"

    For i = 2 To wsReport.Cells(wsReport.Rows.Count, "A").End(xlUp).Row
        If wsReport.Cells(i, "D").Value = "Slow" Then
            txt.WriteLine "| " & wsReport.Cells(i, "A").Value & " | " & wsReport.Cells(i, "B").Value & " | $" & Format(wsReport.Cells(i, "C").Value, "#,##0") & " |"
        End If
    Next i

    txt.Close
    MsgBox "Analysis complete. Report and markdown plan generated.", vbInformation
End Sub
