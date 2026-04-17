function initCheckboxes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  
  sheets.forEach(sheet => {
    const lastRow = sheet.getLastRow();
    if (lastRow < 2) return;
    
    const range = sheet.getRange(2, 1, lastRow - 1, 4);
    
    // Erst alle Zellen auf echtes Boolean FALSE setzen
    const falseValues = Array(lastRow - 1).fill(Array(4).fill(false));
    range.setValues(falseValues);
    
    // Dann Checkbox-Validierung drauf
    const rule = SpreadsheetApp.newDataValidation()
      .requireCheckbox()
      .build();
    range.setDataValidation(rule);
  });
  
  SpreadsheetApp.getUi().alert('✅ Checkboxen erfolgreich initialisiert!');
}