Imports Microsoft.VisualBasic.FileIO

Public Class Form1
    Private Sub Form1_Load(sender As Object, e As EventArgs) Handles MyBase.Load
        RichTextBox1.Clear()
    End Sub

    Public Sub Button1_Click(sender As Object, e As EventArgs) Handles Button1.Click
        OpenFileDialog1.Title = "Select JPMC CSV file"
        OpenFileDialog1.FileName = ""
        OpenFileDialog1.Filter = "CSV Files (*.csv)|*.csv"
        OpenFileDialog1.InitialDirectory = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")
        OpenFileDialog1.Multiselect = False
        TextBox1.Clear()
        OpenFileDialog1.ShowDialog()
        TextBox1.AppendText(OpenFileDialog1.FileName.ToString.Trim & vbNewLine)

        '       REQUIRED COLUMNS IN JPMC FILE
        '       0   ACCOUNT NAME
        '       1   VALUE DATE
        '       2   CREDIT AMOUNT
        '       3   REMARKS 1 <--------------------------------------

    End Sub

    Public Sub Button2_Click(sender As Object, e As EventArgs) Handles Button2.Click
        OpenFileDialog2.Title = "Select NETSUITE CSV file"
        OpenFileDialog2.FileName = ""
        OpenFileDialog2.Filter = "CSV Files (*.csv)|*.csv"
        OpenFileDialog2.InitialDirectory = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")
        OpenFileDialog2.Multiselect = False
        TextBox2.Clear()
        OpenFileDialog2.ShowDialog()
        TextBox2.AppendText(OpenFileDialog2.FileName.ToString.Trim & vbNewLine)

        '        REQUIRED COLUMNS IN NETSUITE FILE
        '        0   CLASS: NAME
        '        1   SPLIT
        '        2   TYPE
        '        3   DATE
        '        4   DOCUMENT NUMBER
        '        5   MEMO
        '        6   DESCRIPTION
        '        7   ENTITY (LINE): ID <---------------------------------------------------
        '        8   Entity (Line): CARRIER_MASTERID
        '        9   TRANSACTION LINK( RECORD IS PARENT): REMARKS 1
        '        10  REMARKS 1
        '        11  DEBIT
        '        12  CREDIT

    End Sub

    Public Sub Button4_Click(sender As Object, e As EventArgs) Handles Button4.Click
        OpenFileDialog3.Title = "Select CONFIG CSV file"
        OpenFileDialog3.FileName = ""
        OpenFileDialog3.Filter = "CSV Files (*.csv)|*.csv"
        OpenFileDialog3.InitialDirectory = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")
        OpenFileDialog3.Multiselect = False
        TextBox3.Clear()
        OpenFileDialog3.ShowDialog()
        TextBox3.AppendText(OpenFileDialog3.FileName.ToString.Trim & vbNewLine)
    End Sub
    Private Sub Button3_Click(sender As Object, e As EventArgs) Handles Button3.Click

        RichTextBox1.Clear()

        Dim CONFIG As New ArrayList
        Dim FinalResult As New ArrayList
        Dim FileReader As IO.StreamReader
        Dim FileWriter As IO.StreamWriter
        Dim ln As String
        Dim time1 As DateTime = DateTime.Now

        If OpenFileDialog1.FileName.ToString.Trim = "" Then
            Exit Sub
        End If
        If OpenFileDialog2.FileName.ToString.Trim = "" Then
            Exit Sub
        End If
        If OpenFileDialog3.FileName.ToString.Trim = "" Then
            Exit Sub
        End If

        Cursor.Current = Cursors.WaitCursor
        FileReader = IO.File.OpenText(OpenFileDialog3.FileName.ToString.Trim)
        While FileReader.Peek <> -1
            ln = FileReader.ReadLine
            CONFIG.Add(ln.ToString.Trim)
        End While
        FileReader.Close()
        FileReader.Dispose()

        'FOR STORING CONFIGURATION VALUES'
        Dim jpmc_bu As String
        Dim jpmc_carrier1 As String
        Dim jpmc_carrier2 As String
        Dim jpmc_carrier3 As String
        Dim netsuite_bu As String
        Dim netsuite_carrier1 As String
        'Dim netsuite_carrier2 As String
        'Dim netsuite_carrier3 As String

        'FOR ADDING EFT/CREDIT AMOUNTS PER COMBINATION'
        Dim JPMC_FILT_CT1 As Decimal
        Dim JPMC_FILT_CT2 As Decimal
        Dim JPMC_FILT_CT3 As Decimal
        Dim JPMC_FILTCT_FINAL As Decimal
        Dim NETSUITE_FILT_CT1 As Decimal
        'Dim NETSUITE_FILT_CT2 As Decimal
        'Dim NETSUITE_FILT_CT3 As Decimal
        Dim NETSUITE_FILTCT_FINAL As Decimal
        Dim JminusN As Decimal
        Dim NETSUITE_JR_TOTAL As Decimal
        Dim NETSUITE_CR_TOTAL As Decimal

        'FOR READ RECORD INCREMENTAL VARIABLE'
        Dim jpmc_flcnt As Integer
        Dim netsuite_flcnt As Integer

        For Each item In CONFIG

            jpmc_bu = ""
            jpmc_carrier1 = ""
            jpmc_carrier2 = ""
            jpmc_carrier3 = ""
            netsuite_bu = ""
            netsuite_carrier1 = ""
            'netsuite_carrier2 = ""
            'netsuite_carrier3 = ""

            If item.ToString.Length = 0 Then
                Continue For
            End If

            jpmc_bu = item.Split(",").GetValue(0).ToString.Trim
            jpmc_carrier1 = item.Split(",").GetValue(1).ToString.Trim
            jpmc_carrier2 = item.Split(",").GetValue(2).ToString.Trim
            jpmc_carrier3 = item.Split(",").GetValue(3).ToString.Trim
            netsuite_bu = item.Split(",").GetValue(4).ToString.Trim
            netsuite_carrier1 = item.Split(",").GetValue(5).ToString.Trim
            'netsuite_carrier2 = item.Split(",").GetValue(6).ToString.Trim
            'netsuite_carrier3 = item.Split(",").GetValue(7).ToString.Trim

            Dim Jcurrentrow As String()
            Dim JNum As Decimal
            Using TFP As New TextFieldParser(OpenFileDialog1.FileName.ToString.Trim)
                TFP.TextFieldType = FieldType.Delimited
                TFP.SetDelimiters(",")
                TFP.HasFieldsEnclosedInQuotes = True
                While Not TFP.EndOfData
                    Jcurrentrow = TFP.ReadFields()
                    jpmc_flcnt = jpmc_flcnt + 1
                    If jpmc_carrier1 IsNot "" Then
                        If Jcurrentrow(0).ToString.IndexOf(jpmc_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Jcurrentrow(3).ToString.IndexOf(jpmc_carrier1, StringComparison.OrdinalIgnoreCase) >= 0 Then
                            JNum = Decimal.Parse(Jcurrentrow(2))
                            JPMC_FILT_CT1 += JNum
                            JNum = 0
                        End If
                    End If
                    If jpmc_carrier2 IsNot "" Then
                        If Jcurrentrow(0).ToString.IndexOf(jpmc_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Jcurrentrow(3).ToString.IndexOf(jpmc_carrier2, StringComparison.OrdinalIgnoreCase) >= 0 Then
                            JNum = Decimal.Parse(Jcurrentrow(2))
                            JPMC_FILT_CT2 += JNum
                            JNum = 0
                        End If
                    End If
                    If jpmc_carrier3 IsNot "" Then
                        If Jcurrentrow(0).ToString.IndexOf(jpmc_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Jcurrentrow(3).ToString.IndexOf(jpmc_carrier3, StringComparison.OrdinalIgnoreCase) >= 0 Then
                            JNum = Decimal.Parse(Jcurrentrow(2))
                            JPMC_FILT_CT3 += JNum
                            JNum = 0
                        End If
                    End If
                End While
            End Using

            Dim Ncurrentrow As String()
            Dim NNum As Decimal
            'If User wants to include JOURNAL entries in the calculation'
            If RadioButton3.Checked = True Then
                Using TFP As New TextFieldParser(OpenFileDialog2.FileName.ToString.Trim)
                    TFP.TextFieldType = FieldType.Delimited
                    TFP.SetDelimiters(",")
                    TFP.HasFieldsEnclosedInQuotes = True
                    While Not TFP.EndOfData
                        Ncurrentrow = TFP.ReadFields()
                        netsuite_flcnt = netsuite_flcnt + 1
                        If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier1, StringComparison.OrdinalIgnoreCase) >= 0 Then
                            If Ncurrentrow(12).ToString.Trim.Length > 0 Then 'For Journal entry where Credit is not NULL'
                                NNum = Decimal.Parse(Ncurrentrow(12))
                                If Ncurrentrow(2).ToString = "Journal" Then
                                    NETSUITE_JR_TOTAL += Decimal.Parse(Ncurrentrow(12))
                                End If
                                If Ncurrentrow(2).ToString = "Cash Receipt" Then
                                    NETSUITE_CR_TOTAL += Decimal.Parse(Ncurrentrow(12))
                                End If
                            End If
                            NETSUITE_FILT_CT1 += NNum
                            NNum = 0
                        End If
                        'If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier2, StringComparison.OrdinalIgnoreCase) >= 0 Then
                        '    If Ncurrentrow(12).ToString.Trim.Length > 0 Then 'For Journal entry where Credit is not NULL'
                        '        NNum = Decimal.Parse(Ncurrentrow(12))
                        '    End If
                        '    NETSUITE_FILT_CT2 += NNum
                        '    NNum = 0
                        'End If
                        'If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier3, StringComparison.OrdinalIgnoreCase) >= 0 Then
                        '    If Ncurrentrow(12).ToString.Trim.Length > 0 Then 'For Journal entry where Credit is not NULL'
                        '        NNum = Decimal.Parse(Ncurrentrow(12))
                        '    End If
                        '    NETSUITE_FILT_CT3 += NNum
                        '    NNum = 0
                        'End If
                    End While
                End Using
            End If

            'If User does not wants to include JOURNAL entries and only wants to consider 'Cash Receipts' in the calculation'
            If RadioButton4.Checked = True Then
                Using TFP As New TextFieldParser(OpenFileDialog2.FileName.ToString.Trim)
                    TFP.TextFieldType = FieldType.Delimited
                    TFP.SetDelimiters(",")
                    TFP.HasFieldsEnclosedInQuotes = True
                    While Not TFP.EndOfData
                        Ncurrentrow = TFP.ReadFields()
                        netsuite_flcnt = netsuite_flcnt + 1
                        If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier1, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(2).ToString = "Cash Receipt" Then
                            NNum = Decimal.Parse(Ncurrentrow(12))
                            NETSUITE_CR_TOTAL += Decimal.Parse(Ncurrentrow(12))
                            NETSUITE_FILT_CT1 += NNum
                            NNum = 0
                        End If
                        'If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier2, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(2).ToString = "Cash Receipt" Then
                        '    NNum = Decimal.Parse(Ncurrentrow(12))
                        '    NETSUITE_FILT_CT2 += NNum
                        '    NNum = 0
                        'End If
                        'If Ncurrentrow(0).ToString.IndexOf(netsuite_bu, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(7).ToString.IndexOf(netsuite_carrier3, StringComparison.OrdinalIgnoreCase) >= 0 And Ncurrentrow(2).ToString = "Cash Receipt" Then
                        '    NNum = Decimal.Parse(Ncurrentrow(12))
                        '    NETSUITE_FILT_CT3 += NNum
                        '    NNum = 0
                        'End If
                    End While
                End Using
            End If

            JPMC_FILTCT_FINAL = (JPMC_FILT_CT1 + JPMC_FILT_CT2 + JPMC_FILT_CT3)
            NETSUITE_FILTCT_FINAL = NETSUITE_FILT_CT1 '+ NETSUITE_FILT_CT2 + NETSUITE_FILT_CT3
            JminusN = NETSUITE_FILTCT_FINAL - JPMC_FILTCT_FINAL
            FinalResult.Add(netsuite_bu.ToString.Trim.ToUpper & "," & netsuite_carrier1.ToString.Trim.ToUpper & "," & JPMC_FILT_CT1 & "," & JPMC_FILT_CT2 & "," & JPMC_FILT_CT3 & "," & JPMC_FILTCT_FINAL & "," & NETSUITE_CR_TOTAL & "," & NETSUITE_JR_TOTAL & "," & NETSUITE_FILTCT_FINAL & "," & JminusN)

            JPMC_FILT_CT1 = 0
            JPMC_FILT_CT2 = 0
            JPMC_FILT_CT3 = 0
            JPMC_FILTCT_FINAL = 0
            NETSUITE_FILT_CT1 = 0
            'NETSUITE_FILT_CT2 = 0
            'NETSUITE_FILT_CT3 = 0
            NETSUITE_FILTCT_FINAL = 0
            JminusN = 0

            NETSUITE_JR_TOTAL = 0
            NETSUITE_CR_TOTAL = 0

        Next

        'Perform grouping sum of JPMC, wherever same BU's are having multiple bank accounts'
        FinalResult.Sort()
        If RadioButton1.Checked = True Then
            For i As Integer = 0 To FinalResult.Count - 1 Step 1
                If i = FinalResult.Count - 1 Then
                    Exit For
                End If
                If String.Concat(FinalResult.Item(i).ToString.Split(",").GetValue(0), FinalResult.Item(i).ToString.Split(",").GetValue(1)) = String.Concat(FinalResult.Item(i + 1).ToString.Split(",").GetValue(0), FinalResult.Item(i + 1).ToString.Split(",").GetValue(1)) Then
                    FinalResult.Item(i) = FinalResult.Item(i).ToString.Split(",").GetValue(0) & "," & FinalResult.Item(i).ToString.Split(",").GetValue(1) & "," &
                    (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(2)) + Decimal.Parse(FinalResult.Item(i + 1).ToString.Split(",").GetValue(2))) & "," &
                    (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(3)) + Decimal.Parse(FinalResult.Item(i + 1).ToString.Split(",").GetValue(3))) & "," &
                    (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(4)) + Decimal.Parse(FinalResult.Item(i + 1).ToString.Split(",").GetValue(4))) & "," &
                    (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(5)) + Decimal.Parse(FinalResult.Item(i + 1).ToString.Split(",").GetValue(5))) & "," &
                    Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(6)) & "," &
                    Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(7)) & "," &
                    Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(8)) & "," &
                    (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(6))) - (Decimal.Parse(FinalResult.Item(i).ToString.Split(",").GetValue(5)) + Decimal.Parse(FinalResult.Item(i + 1).ToString.Split(",").GetValue(5)))
                End If
            Next
            'Delete Recurring Record from the Array which are already considered in SUM above, which is the 2nd Bank Name of the same BU'
            For i As Integer = FinalResult.Count - 1 To 0 Step -1
                If i = 0 Then
                    Exit For
                End If
                If String.Concat(FinalResult.Item(i).ToString.Split(",").GetValue(0), FinalResult.Item(i).ToString.Split(",").GetValue(1)) = String.Concat(FinalResult.Item(i - 1).ToString.Split(",").GetValue(0), FinalResult.Item(i - 1).ToString.Split(",").GetValue(1)) Then
                    FinalResult.RemoveAt(i)
                End If
            Next
            FinalResult.Sort()
        End If

        If RadioButton2.Checked = True Then
            'Nothing Special will happen, just that above calculation of combining the counts for multiple bank accounts will be skipped, and remaining iteration will happen as usual'
        End If

        FileWriter = IO.File.CreateText(System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads") & "\Output.csv")
        FileWriter.WriteLine("BU" & "," & "CRG" & "," & "JPMC_CR1" & "," & "JPMC_CR2" & "," & "JPMC_CR3" & "," & "JPMC_TOTAL" & "," & "NETSUITE_CASH" & "," & "NETSUITE_JOURNAL" & "," & "NETSUITE_TOTAL" & "," & "DIFFERENCE")
        For Each item In FinalResult
            FileWriter.WriteLine(item)
        Next
        FinalResult.Clear()
        FileWriter.Close()
        FileWriter.Dispose()

        Dim time2 As DateTime = DateTime.Now
        Dim time3 As TimeSpan = time2 - time1

        RichTextBox1.AppendText("Processing Complete" & vbNewLine)
        RichTextBox1.AppendText(vbNewLine & "JPMC records parsed: " & jpmc_flcnt)
        RichTextBox1.AppendText(vbNewLine & "NetSuite records parsed: " & netsuite_flcnt)
        RichTextBox1.AppendText(vbNewLine & "Configurations parsed: " & CONFIG.Count)
        RichTextBox1.AppendText(vbNewLine & "Processing time: " & Math.Round(time3.TotalSeconds) & " seconds")
        Cursor.Current = Cursors.Default
        MsgBox("Done", MsgBoxStyle.OkOnly, "Result")

    End Sub

    Private Sub ExitToolStripMenuItem_Click(sender As Object, e As EventArgs) Handles ExitToolStripMenuItem.Click
        End
    End Sub

End Class
