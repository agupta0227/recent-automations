Public Class Form3

    Public FileName As String
    Public AIFiles As New ArrayList
    Public LumReader As IO.StreamReader
    Public LumWriter As IO.StreamWriter
    Public line As String
    Public LumArray As New ArrayList
    Public LumBUList As New ArrayList
    Private Sub Button1_Click(sender As Object, e As EventArgs) Handles Button1.Click

        OpenFileDialog1.Title = "Please select the CSIL.TXT file"
        OpenFileDialog1.FileName = ""
        OpenFileDialog1.Filter = "TXT Files (*.TXT)|*.TXT"
        OpenFileDialog1.InitialDirectory = "C:\"
        OpenFileDialog1.Multiselect = True
        OpenFileDialog1.ShowDialog()

        AIFiles.Clear()
        For Each item In OpenFileDialog1.FileNames
            AIFiles.Add(item.ToString.Trim)
        Next
        For Each item In OpenFileDialog1.SafeFileNames
            TextBox1.AppendText(item & vbCrLf)
        Next
        TextBox1.SelectionStart = 0
        TextBox1.ScrollToCaret()

    End Sub

    Private Sub Button2_Click(sender As Object, e As EventArgs) Handles Button2.Click

        LumArray.Clear()
        LumBUList.Clear()
        If AIFiles.Count = 0 Then
            Exit Sub
        End If

        Cursor = Cursors.WaitCursor
        Application.DoEvents()
        Dim Flname As String
        Dim BUname As String
        Try
            For Each fl In AIFiles
                LumReader = IO.File.OpenText(fl)
                Flname = ""
                Flname = IO.Path.GetFileName(fl)
                While LumReader.Peek <> -1
                    line = LumReader.ReadLine
                    LumArray.Add(Flname & ";" & line)
                End While
                LumReader.Close()
                LumReader.Dispose()
            Next
        Catch ex As Exception
            MessageBox.Show("Please select appropriate file!!", "Information", MessageBoxButtons.OK)
            Cursor = Cursors.Default
            Exit Sub
        End Try

        For i As Integer = 0 To LumArray.Count - 1
            If LumArray.Item(i).ToString.Trim.Split(";").GetValue(1).ToString.Trim.Contains("(855) 664-5517") Then
                BUname = ""
                BUname = LumArray.Item(i + 3).ToString.Trim.Split(";").GetValue(1).ToString.Trim
                If BUname.StartsWith("1 ") Then
                    BUname = BUname.Substring(2, BUname.Length - 2)
                    LumBUList.Add(BUname & "%" & i + 4 & "%" & LumArray.Item(i).ToString.Trim.Split(";").GetValue(0).ToString.Trim)
                End If
            End If
        Next
        LumBUList.Sort()

        If CheckBox1.CheckState = CheckState.Checked Then
            LumWriter = IO.File.CreateText(Environment.GetFolderPath(Environment.SpecialFolder.Desktop) & "\" & "CsilFileParser_Debug_" & DateTime.Now.Ticks & ".txt")
            For Each item In LumBUList
                LumWriter.WriteLine(item.ToString.Trim)
            Next
            LumWriter.Close()
            LumWriter.Dispose()
        End If

        Dim ht As New Hashtable
        For Each item In LumBUList
            item = item.ToString.Split("%").GetValue(0).ToString.Trim
            ht.Item(item) = Nothing
        Next
        Dim temp As New ArrayList(ht.Keys)
        Dim LumBUList_Distinct As New ArrayList
        For Each item In temp
            LumBUList_Distinct.Add(item)
        Next
        LumBUList_Distinct.Sort()

        ListBox1.Items.Clear()
        For Each item In LumBUList_Distinct
            ListBox1.Items.Add(item.ToString.Trim)
        Next
        ListBox1.Sorted = True
        Cursor = Cursors.Default
        LumBUList_Distinct.Clear()

    End Sub

    Private Sub Button3_Click(sender As Object, e As EventArgs) Handles Button3.Click

        Dim FindBU As New ArrayList
        For Each item In ListBox1.SelectedItems
            FindBU.Add(item)
        Next

        If FindBU.Count = 0 Then
            Exit Sub
        End If

        Dim GetLineNum As New ArrayList
        Dim GetData As New ArrayList

        For Each BU In FindBU

            GetLineNum.Clear()
            For Each item In LumBUList
                If item.ToString.Contains(BU.ToString) Then
                    GetLineNum.Add(item.ToString.Split("%").GetValue(1) - 1)
                End If
            Next

            GetData.Clear()
            For Each ln In GetLineNum
                Do Until LumArray.Item(ln).ToString.Trim.Split(";").GetValue(1).ToString.Trim.StartsWith("(855) 664-5517")
                    GetData.Add(LumArray.Item(ln).ToString.Split(";").GetValue(1).ToString)
                    ln += 1
                Loop
                GetData.Add("%#%#%")
            Next

            BU = BU.Substring(0, BU.Length - 9).ToString.Trim
            LumWriter = IO.File.CreateText(Environment.GetFolderPath(Environment.SpecialFolder.Desktop) & "\" & "CsilFileParser_" & BU & "_" & DateTime.Now.Ticks & ".txt")
            For Each item In GetData
                LumWriter.WriteLine(item)
            Next
            LumWriter.Close()
            LumWriter.Dispose()
            BU = ""

        Next
        MessageBox.Show("Data Extraction Complete", "Information", MessageBoxButtons.OK)

    End Sub

    Private Sub ExitToolStripMenuItem_Click(sender As Object, e As EventArgs) Handles ExitToolStripMenuItem.Click
        Main.Show()
        Me.Hide()
    End Sub

    Private Sub Form3_FormClosing(sender As Object, e As FormClosingEventArgs) Handles MyBase.FormClosing
        Main.Show()
        Me.Hide()
    End Sub

End Class