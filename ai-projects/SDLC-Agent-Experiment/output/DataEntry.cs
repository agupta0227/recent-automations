// ========================================================================
// FILE    : DataEntry.cs
// VERSION : 1
// CREATED : 2026-05-21 15:55:02
// ========================================================================

```csharp
using System;

namespace SalesApp
{
    public class SalesRecord
    {
        public DateTime Date { get; set; } 
        public string OrganizationName { get; set; }
        public string CarrierName { get; set; }
        public decimal CommissionAmount { get; set; }
        public string Notes { get; set; }

        // Constructor for the SalesRecord class (implementation omitted for brevity)
    }

    public class DataEntry
    {
        private SalesRecord _salesRecord = new SalesRecord(); 

        public void CreateNewRecord()
        {
            _salesRecord.Date = DateTime.Now;
            _salesRecord.OrganizationName = "Company A";
            _salesRecord.CarrierName = "FedEx";
            _salesRecord.CommissionAmount = 100.0m;
            _salesRecord.Notes = "Test Notes";

        }
    }
}
```