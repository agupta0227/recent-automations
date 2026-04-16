import React, { useState, useEffect } from "react";
import "./styles.css";

const DAILY_SUPPLEMENTS = [
  { id: "omega3", name: "Omega-3 500mg" },
  { id: "coq10", name: "CoQ10 400mg" },
  { id: "amlodipine", name: "Amlodipine 5mg" },
  { id: "lcarnitine", name: "L-Carnitine 500mg" },
  { id: "acai", name: "Acai Berry 6000mg" },
];

const WEEKLY_SUPPLEMENTS = [
  { id: "letrozole", name: "Letrozole 2.5mg", days: ["Tuesday", "Saturday"] },
  { id: "zinc", name: "Zinc 50mg", days: ["Sunday"] },
  { id: "clomid", name: "Clomid 50mg", days: ["Thursday"] },
];

const ALL_SUPPLEMENTS = [...DAILY_SUPPLEMENTS, ...WEEKLY_SUPPLEMENTS];

const DAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const EJACULATION_START = new Date(2026, 3, 13); // Apr 13 2026 LOCAL
const START_DATE = "2026-04-11";
const END_DATE = "2026-07-30";

// ⭐ FIX: Parse YYYY-MM-DD as LOCAL date (not UTC)
function parseLocalDate(str) {
  const [y, m, d] = str.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function isWeeklyScheduled(sup, dayName) {
  return sup.days ? sup.days.includes(dayName) : false;
}

function isSupplementScheduled(sup, dayName) {
  return sup.days ? sup.days.includes(dayName) : true;
}

function generateDays(start = START_DATE, end = END_DATE) {
  const days = [];

  const startDate = parseLocalDate(start);
  const endDate = parseLocalDate(end);

  const totalDays = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));

  for (let i = 0; i <= totalDays; i++) {
    // ⭐ FIX: fresh local date each iteration
    const d = new Date(startDate.getTime());
    d.setDate(startDate.getDate() + i);

    const dateStr = d.toLocaleDateString("en-CA"); // YYYY-MM-DD LOCAL
    const dayStr = DAY_NAMES[d.getDay()];

    const taken = {};
    ALL_SUPPLEMENTS.forEach((s) => (taken[s.id] = false));

    const diffDays = Math.floor(
      (d - EJACULATION_START) / (1000 * 60 * 60 * 24)
    );
    const ejaculationDue = diffDays >= 0 && diffDays % 3 === 0;

    days.push({
      date: dateStr,
      day: dayStr,
      selectedType: "AG1",
      takenType: false,
      taken,
      ejaculationDue,
      ejaculationDone: false,
      status: false,
    });
  }

  return days;
}

function computeStatus(day) {
  const allDailyTaken = DAILY_SUPPLEMENTS.every((s) => day.taken[s.id]);

  const allWeeklyTaken = WEEKLY_SUPPLEMENTS.every((s) => {
    const scheduled = isWeeklyScheduled(s, day.day);
    return !scheduled || day.taken[s.id];
  });

  const typeTaken = day.takenType;
  const ejaculationOk = !day.ejaculationDue || day.ejaculationDone;

  return allDailyTaken && allWeeklyTaken && typeTaken && ejaculationOk;
}

function App() {
  const [days, setDays] = useState(() => {
    const saved = localStorage.getItem("med-tracker-days-v6");
    return saved ? JSON.parse(saved) : generateDays();
  });

  const [showTodayOnly, setShowTodayOnly] = useState(false);

  useEffect(() => {
    localStorage.setItem("med-tracker-days-v6", JSON.stringify(days));
  }, [days]);

  // ⭐ FIX: Today in LOCAL time
  const todayStr = new Date().toLocaleDateString("en-CA");

  const updateDay = (date, updater) => {
    setDays((prev) =>
      prev.map((d) => {
        if (d.date !== date) return d;
        const updated = updater(d);
        return { ...updated, status: computeStatus(updated) };
      })
    );
  };

  const toggleSupplement = (date, supId) => {
    updateDay(date, (d) => ({
      ...d,
      taken: { ...d.taken, [supId]: !d.taken[supId] },
    }));
  };

  const updateType = (date, value) => {
    updateDay(date, (d) => ({ ...d, selectedType: value }));
  };

  const toggleTypeTaken = (date) => {
    updateDay(date, (d) => ({ ...d, takenType: !d.takenType }));
  };

  const toggleEjaculation = (date) => {
    updateDay(date, (d) => {
      if (!d.ejaculationDue) return d;
      return { ...d, ejaculationDone: !d.ejaculationDone };
    });
  };

  const filteredDays = showTodayOnly
    ? days.filter((d) => d.date === todayStr)
    : days;

  const last7Days = days.slice(-7);
  const adherence = (() => {
    const total = last7Days.length;
    const done = last7Days.filter((d) => d.status).length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    return { total, done, pct };
  })();

  return (
    <div className="app">
      <h1>Medicine Supplement Tracker</h1>

      <div className="legend">
        <div>
          <strong>Legend:</strong>
        </div>
        <div>✅ = taken & scheduled</div>
        <div>❌ = scheduled, not taken</div>
        <div>⚪ = not scheduled</div>
        <div>❗ = due (every 3 days)</div>
      </div>

      <div className="controls">
        <label>
          <input
            type="checkbox"
            checked={showTodayOnly}
            onChange={(e) => setShowTodayOnly(e.target.checked)}
          />
          Show today only
        </label>
        <div className="summary">
          Last 7 days: {adherence.done}/{adherence.total} days done (
          {adherence.pct}%)
        </div>
      </div>

      <table className="tracker-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Day</th>
            <th>AG1 / Kirkland</th>
            {DAILY_SUPPLEMENTS.map((s) => (
              <th key={s.id}>{s.name}</th>
            ))}
            {WEEKLY_SUPPLEMENTS.map((s) => (
              <th key={s.id}>{s.name}</th>
            ))}
            <th>Every 3 days</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          {filteredDays.map((day, index) => {
            const prev = filteredDays[index - 1];
            const monthChanged =
              prev && prev.date.slice(0, 7) !== day.date.slice(0, 7);

            return (
              <React.Fragment key={day.date}>
                {monthChanged && (
                  <tr className="month-break">
                    <td colSpan="100%">— End of {prev.date.slice(0, 7)} —</td>
                  </tr>
                )}

                <tr className={day.status ? "row-done" : ""}>
                  <td className="date-cell">{day.date}</td>
                  <td>{day.day}</td>

                  <td className="type-cell">
                    <select
                      value={day.selectedType}
                      onChange={(e) => updateType(day.date, e.target.value)}
                    >
                      <option value="AG1">AG1</option>
                      <option value="Kirkland">Kirkland</option>
                    </select>
                    <span
                      className="type-toggle"
                      onClick={() => toggleTypeTaken(day.date)}
                    >
                      {day.takenType ? "✅" : "❌"}
                    </span>
                  </td>

                  {DAILY_SUPPLEMENTS.map((s) => (
                    <td
                      key={s.id}
                      className="cell"
                      onClick={() => toggleSupplement(day.date, s.id)}
                    >
                      {day.taken[s.id] ? "✅" : "❌"}
                    </td>
                  ))}

                  {WEEKLY_SUPPLEMENTS.map((s) => {
                    const scheduled = isSupplementScheduled(s, day.day);
                    const symbol = !scheduled
                      ? "⚪"
                      : day.taken[s.id]
                      ? "✅"
                      : "❌";

                    return (
                      <td
                        key={s.id}
                        className={scheduled ? "cell" : "cell-disabled"}
                        onClick={
                          scheduled
                            ? () => toggleSupplement(day.date, s.id)
                            : undefined
                        }
                      >
                        {symbol}
                      </td>
                    );
                  })}

                  <td
                    className={day.ejaculationDue ? "cell" : "cell-disabled"}
                    onClick={
                      day.ejaculationDue
                        ? () => toggleEjaculation(day.date)
                        : undefined
                    }
                  >
                    {!day.ejaculationDue
                      ? "⚪"
                      : day.ejaculationDone
                      ? "✅"
                      : "❗"}
                  </td>

                  <td>{day.status ? "✅" : ""}</td>
                </tr>
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default App;
