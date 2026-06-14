/* ============================================================
   הגדרות מס הכנסה — נכון לשנת 2026
   ------------------------------------------------------------
   קובץ זה ניתן לעריכה. אם מדרגות המס או שווי נקודת הזיכוי
   משתנים בעתיד — עדכן כאן בלבד, וכל המחשבונים יתעדכנו.

   מקור: רשות המסים בישראל (טבלת מדרגות מס שנתיות).
   המדרגה העליונה (50%) כוללת את מס היסף (3%) שחל על
   הכנסה שנתית מעל 721,560 ₪.
   ============================================================ */

const TAX_CONFIG = {
  year: 2026,

  // שווי נקודת זיכוי אחת — 242 ₪ לחודש × 12 = 2,904 ₪ לשנה
  creditPointAnnual: 2904,

  // ברירת מחדל לנקודות זיכוי לתושב ישראל (2.25 נקודות)
  defaultCreditPoints: 2.25,

  // מדרגות מס הכנסה שנתיות (₪).
  //   upTo = תקרת המדרגה בש"ח לשנה (null = "ומעלה")
  //   rate = שיעור המס במדרגה זו
  brackets: [
    { upTo: 84120,  rate: 0.10 },
    { upTo: 120720, rate: 0.14 },
    { upTo: 193800, rate: 0.20 },
    { upTo: 269280, rate: 0.31 },
    { upTo: 560280, rate: 0.35 },
    { upTo: 721560, rate: 0.47 },
    { upTo: null,   rate: 0.50 },
  ],
};

/* ---------- פונקציות עזר לחישוב מס ---------- */

// מס שולי-מצטבר לפי המדרגות על הכנסה חייבת נתונה (לפני נקודות זיכוי)
function bracketTax(taxableIncome) {
  let tax = 0, prev = 0;
  for (const b of TAX_CONFIG.brackets) {
    const cap = b.upTo === null ? Infinity : b.upTo;
    if (taxableIncome > prev) {
      tax += (Math.min(taxableIncome, cap) - prev) * b.rate;
      prev = cap;
    } else break;
  }
  return tax;
}

// מס הכנסה בפועל אחרי קיזוז נקודות זיכוי (לא יורד מתחת ל-0)
function incomeTaxAfterCredits(taxableIncome, creditPoints) {
  const gross = bracketTax(taxableIncome);
  const credit = creditPoints * TAX_CONFIG.creditPointAnnual;
  return Math.max(0, gross - credit);
}
