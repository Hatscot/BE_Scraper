function onOpen() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  sheets.forEach(sheet => addCheckboxesToSheet(sheet));
}

function addCheckboxesToSheet(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;
  const range = sheet.getRange(2, 1, lastRow - 1, 4);
  const rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  range.setDataValidation(rule);
}

function onEdit(e) {
  const range = e.range;
  const sheet = range.getSheet();
  const row = range.getRow();
  const col = range.getColumn();
  const value = range.getValue();

  if (row < 2 || col < 1 || col > 4) return;
  if (value !== true) return;

  // Sicherheits-Check: Nur eine Checkbox darf true sein
  const checkboxValues = sheet.getRange(row, 1, 1, 4).getValues()[0];
  const trueCount = checkboxValues.filter(v => v === true).length;

  if (trueCount > 1) {
    range.setValue(false);
    SpreadsheetApp.getUi().alert(
      '⚠️ Fehler: Nur eine Checkbox pro Zeile erlaubt!\n\n' +
      'Bitte zuerst die andere Checkbox deaktivieren.'
    );
    return;
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const targetMap = { 1: "Kauf", 2: "Beobachten", 3: "Gelöscht", 4: "Archiv" };
  const targetName = targetMap[col];
  if (!targetName) return;

  let targetSheet = ss.getSheetByName(targetName);
  if (!targetSheet) {
    targetSheet = ss.insertSheet(targetName);
    copyRowToSheet(sheet, 1, targetSheet, 1, sheet.getLastColumn());
    addCheckboxesToSheet(targetSheet);
  }

  const lastCol = sheet.getLastColumn();
  const newRow = targetSheet.getLastRow() + 1;

  // Zeile ins Zielblatt kopieren
  copyRowToSheet(sheet, row, targetSheet, newRow, lastCol);

  // Checkboxen in Zielzeile zurücksetzen
  const checkboxRange = targetSheet.getRange(newRow, 1, 1, 4);
  checkboxRange.setValues([[false, false, false, false]]);
  const rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  checkboxRange.setDataValidation(rule);

  // Originalzeile löschen
  sheet.deleteRow(row);
}

function copyRowToSheet(sourceSheet, sourceRow, targetSheet, targetRow, lastCol) {
  const sourceRange = sourceSheet.getRange(sourceRow, 1, 1, lastCol);
  const values = sourceRange.getValues();
  const richTextValues = sourceRange.getRichTextValues();
  const numberFormats = sourceRange.getNumberFormats();

  const targetRange = targetSheet.getRange(targetRow, 1, 1, lastCol);

  // Zuerst Werte und Formatierung setzen
  targetRange.setValues(values);
  targetRange.setNumberFormats(numberFormats);

  // RichText nur für Zellen mit echten Links setzen
  for (let c = 0; c < lastCol; c++) {
    const rt = richTextValues[0][c];
    if (rt && rt.getLinkUrl() !== null) {
      targetSheet.getRange(targetRow, c + 1).setRichTextValue(rt);
    }
  }
}

function initCheckboxes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();

  sheets.forEach(sheet => {
    const lastRow = sheet.getLastRow();
    if (lastRow < 2) return;
    const range = sheet.getRange(2, 1, lastRow - 1, 4);
    const falseValues = Array(lastRow - 1).fill(null).map(() => Array(4).fill(false));
    range.setValues(falseValues);
    const rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
    range.setDataValidation(rule);
  });

  SpreadsheetApp.getUi().alert('✅ Checkboxen erfolgreich initialisiert!');
}