// ========================================================================
// FILE    : SalesApp.MainForm.cs
// VERSION : 4
// CREATED : 2026-05-21 15:41:14
// ========================================================================

```csharp
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SalesApp
{
    public partial class MainForm : Form
    {
        // CSV file path
        private string csvFilePath = "SalesData.csv"; 

        public MainForm()
        {
            InitializeComponent();
        }

        private void btnAddRecord_Click(object sender, EventArgs e)
        {
            try
            {
                // Validate input fields for empty values and data types
                if (string.IsNullOrEmpty(txtDate.Text) || string.IsNullOrEmpty(txtOrgName.Text) || 
                    string.IsNullOrEmpty(txtCarrierName.Text) || 
                    double.TryParse(txtCommission.Text, out double commission) == false)
                {
                    MessageBox.Show("Please fill in all required fields.");
                    return;
                }

                // Add new record to the data
                string[] data = { txtDate.Text, txtOrgName.Text, txtCarrierName.Text, 
                                    txtCommission.Text, txtNotes.Text };

                try
                {
                    using (StreamWriter writer = File.AppendText(csvFilePath))
                    {
                        foreach (var item in data)
                        {
                            writer.WriteLine(item);
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}");
                }

                // Display success message
                MessageBox.Show("New record added successfully.");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred: {ex.Message}");
            }
        }
    }
}