// ========================================================================
// FILE    : ViewRecords.cs
// VERSION : 1
// CREATED : 2026-05-21 15:55:02
// ========================================================================

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Forms;

namespace SalesApp
{
    public class ViewRecords
    {
        private List<SalesRecord> _salesRecords = new List<SalesRecord>(); 

        public void DisplayRecords()
        {
            // Implement logic to display records in a listbox (implementation omitted for brevity)
            ListView listView = new ListView(); 
            listView.Items.Clear();
            foreach (var record in _salesRecords)
            {
                listView.Items.Add(record); // Replace with actual logic to populate the list view
            }
        }

    }
}