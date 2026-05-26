// ========================================================================
// FILE    : CSVWriter.cs
// VERSION : 1
// CREATED : 2026-05-21 15:55:02
// ========================================================================

```csharp
using System;
using System.IO;

namespace SalesApp
{
    public class CSVWriter
    {
        private string _filePath; 

        public CSVWriter(string filePath)
        {
            _filePath = filePath;
        }

        public void WriteData(List<SalesRecord> salesRecords)
        {
            try
            {
                using (StreamWriter writer = new StreamWriter(_filePath))
                {
                    foreach (var record in salesRecords)
                    {
                        writer.WriteLine($"{record.Date:yyyy-MM-dd}"); // Example format for writing data to CSV
                        writer.WriteLine($"Organization Name: {record.OrganizationName}"); 
                        writer.WriteLine($"Carrier Name: {record.CarrierName}");
                        writer.WriteLine($"Commission Amount: {record.CommissionAmount}");
                        writer.WriteLine($"Notes: {record.Notes}");
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error writing data to CSV file: {ex.Message}");
            }
        }
    }
}
```