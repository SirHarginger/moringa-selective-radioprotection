-- Shared helpers for the LaTeX build of the French Embassy report.
--
-- Loaded by report.lua and datatables.lua with dofile(). Pure functions only: no file is
-- written here, and nothing here interprets scientific content.

local M = {}

--- Stop the build with a message that names the problem. pandoc exits non-zero.
function M.fail(msg)
  error('\n[latex build] ' .. msg .. '\n', 0)
end

function M.read_file(path)
  local fh, err = io.open(path, 'rb')
  if not fh then M.fail('cannot read ' .. path .. ' (' .. tostring(err) .. ')') end
  local text = fh:read('a')
  fh:close()
  return text
end

function M.write_file(path, text)
  local fh, err = io.open(path, 'wb')
  if not fh then M.fail('cannot write ' .. path .. ' (' .. tostring(err) .. ')') end
  fh:write(text)
  fh:close()
end

--- Parse RFC 4180 CSV (quoted fields, doubled quotes, embedded commas and newlines).
-- Returns the header (list of names) and the rows (list of {name = value} tables, with
-- the original order kept in row._order). Values are returned exactly as stored.
function M.parse_csv(text, source)
  source = source or 'CSV'
  text = text:gsub('^\239\187\191', '') -- UTF-8 byte-order mark
  local records, record, field = {}, {}, {}
  local i, n, in_quotes = 1, #text, false
  while i <= n do
    local c = text:sub(i, i)
    if in_quotes then
      if c == '"' then
        if text:sub(i + 1, i + 1) == '"' then
          field[#field + 1] = '"'
          i = i + 1
        else
          in_quotes = false
        end
      else
        field[#field + 1] = c
      end
    elseif c == '"' then
      in_quotes = true
    elseif c == ',' then
      record[#record + 1] = table.concat(field)
      field = {}
    elseif c == '\n' or c == '\r' then
      if c == '\r' and text:sub(i + 1, i + 1) == '\n' then i = i + 1 end
      record[#record + 1] = table.concat(field)
      records[#records + 1] = record
      record, field = {}, {}
    else
      field[#field + 1] = c
    end
    i = i + 1
  end
  if in_quotes then M.fail(source .. ': unterminated quoted field') end
  if #field > 0 or #record > 0 then
    record[#record + 1] = table.concat(field)
    records[#records + 1] = record
  end
  if #records == 0 then M.fail(source .. ': file is empty') end

  local header = records[1]
  local seen = {}
  for _, name in ipairs(header) do
    if seen[name] then M.fail(source .. ': duplicate column "' .. name .. '"') end
    seen[name] = true
  end
  local rows = {}
  for r = 2, #records do
    local rec = records[r]
    if not (#rec == 1 and rec[1] == '') then -- ignore blank lines
      if #rec ~= #header then
        M.fail(string.format('%s: row %d has %d fields, header has %d', source, r, #rec,
          #header))
      end
      local row = {}
      for k, name in ipairs(header) do row[name] = rec[k] end
      rows[#rows + 1] = row
    end
  end
  return header, rows
end

--- Collapse internal whitespace (including newlines inside quoted CSV cells) and trim.
function M.squash(s)
  return (s:gsub('%s+', ' '):gsub('^ ', ''):gsub(' $', ''))
end

local ESCAPES = {
  ['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}', ['$'] = '\\$',
  ['&'] = '\\&', ['#'] = '\\#', ['%'] = '\\%', ['_'] = '\\_',
  ['^'] = '\\textasciicircum{}', ['~'] = '\\textasciitilde{}',
}

--- Escape plain text for LaTeX. Unicode is passed through (LuaLaTeX + fontspec).
function M.escape(s)
  return (s:gsub('[\\{}%$&#%%_%^~]', ESCAPES))
end

--- Escape, then allow line breaks after _ / : . and - inside long tokens (identifiers,
-- DOIs, gene-set names) so narrow table columns never overflow.
function M.breakable(s)
  local out = {}
  for token, space in s:gmatch('(%S+)(%s*)') do
    if utf8.len(token) and utf8.len(token) > 12 and not token:match('^[%d%.%-]+$') then
      local pieces = {}
      for piece in token:gmatch('[^_/:%.%-]*[_/:%.%-]?') do
        if piece ~= '' then pieces[#pieces + 1] = M.escape(piece) end
      end
      out[#out + 1] = table.concat(pieces, '\\allowbreak{}')
    else
      out[#out + 1] = M.escape(token)
    end
    if space ~= '' then out[#out + 1] = ' ' end
  end
  return table.concat(out)
end

--- Characters that would break \url-style verbatim arguments.
function M.url_safe(s)
  return not s:find('[%%#{}\\%^~]')
end

--- Numbers are shown with a typographic minus sign.
function M.minus(s)
  return (s:gsub('^%-', '\u{2212}'))
end

--- Lower-case alphanumeric fingerprint, used to compare captions that differ only in
-- markup, quote style or spacing.
function M.fingerprint(s)
  return (s:lower():gsub('[^%w]', ''))
end

--- "Figure 1" -> "fig-01", "Figure S2" -> "fig-s02", "Table C1" -> "tab-c1".
function M.figure_label(report_label)
  local supp, num = report_label:match('^Figure (S?)(%d+)$')
  if not num then M.fail('unrecognised figure label "' .. report_label .. '"') end
  return string.format('fig-%s%02d', supp:lower(), tonumber(num))
end

function M.table_label(report_label)
  local id = report_label:match('^Table ([CRS]?%d+)$')
  if not id then M.fail('unrecognised table label "' .. report_label .. '"') end
  return 'tab-' .. id:lower()
end

return M
