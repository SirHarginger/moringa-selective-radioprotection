-- datatables.lua: typeset every table listed in table_manifest.csv for Appendix H.
--
-- Run by build.sh as a pandoc filter on an empty document. For each manifest entry it
-- reads the CSV named there (exact values, RFC 4180 parsing), formats the columns chosen
-- in table_specs.lua and writes a booktabs longtable. Captions come from the generated
-- captions.md of the publication tables where one exists, otherwise from the manifest
-- title. The build fails on a missing file, a missing column, a non-numeric value in a
-- numeric column, a "constant" column that is not constant, or a manifest entry whose
-- status is not "generated".
--
-- Side outputs (paths passed as metadata by build.sh):
--   labels-file   expected label -> number pairs, checked against the .aux after LaTeX
--   sources-file  every input file of the report, for the SHA-256 provenance table

PANDOC_VERSION:must_be_at_least '3.1'

local here = pandoc.path.directory(PANDOC_SCRIPT_FILE)
local lib = dofile(pandoc.path.join { here, 'lib.lua' })
local specs = dofile(pandoc.path.join { here, 'table_specs.lua' })
local stringify = pandoc.utils.stringify
local fail = lib.fail

local function meta_string(meta, key)
  if meta[key] == nil then fail('missing metadata "' .. key .. '" (passed by build.sh)') end
  return stringify(meta[key])
end

local function to_latex(inlines)
  local out = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), 'latex')
  return (out:gsub('%s+$', ''))
end

-- Output mode, set from the "table-format" metadata: 'latex' (Appendix H of the LaTeX
-- edition) or 'plain' (pandoc tables for the DOCX edition, same values and layout spec).
local PLAIN = false
local function esc(s) return PLAIN and s or lib.escape(s) end
local function path(s) return PLAIN and s or ('\\reportpath{' .. s .. '}') end

------------------------------------------------------------------------------------------
-- Captions from the generated captions.md
------------------------------------------------------------------------------------------

local function load_captions(path)
  local doc = pandoc.read(lib.read_file(path), 'markdown')
  local captions = {}
  for _, b in ipairs(doc.blocks) do
    if b.t == 'Para' then
      local text = stringify(b.content)
      local key = text:match('^(Table [CRS]?%d+)%.') or text:match('^([%w_]+)%.')
          or text:match('^(Common notes)%.')
      if key then
        local inl = pandoc.List(b.content)
        local removed = ''
        while #inl > 0 and removed ~= key .. '.' do
          removed = removed .. stringify(inl[1])
          inl:remove(1)
        end
        if removed ~= key .. '.' then fail(path .. ': cannot parse caption "' .. key .. '"') end
        while inl[1] and (inl[1].t == 'Space' or inl[1].t == 'SoftBreak') do inl:remove(1) end
        captions[key] = inl
      end
    end
  end
  return captions
end

------------------------------------------------------------------------------------------
-- Cell formatting
------------------------------------------------------------------------------------------

local function format_number(value, decimals, where)
  local n = tonumber(value)
  if not n then fail(where .. ': "' .. value .. '" is not a number') end
  local s
  if decimals == nil then
    if n ~= math.floor(n) then fail(where .. ': "' .. value .. '" is not an integer') end
    s = string.format('%d', n)
  elseif math.abs(n) >= 1 and n == math.floor(n) then
    s = string.format('%d', n) -- counts in a decimal column, e.g. "repeats > 0"
  else
    s = string.format('%.' .. decimals .. 'f', n)
    if s:match('^%-0%.0*$') then s = s:sub(2) end -- no "-0.000"
  end
  return lib.minus(s)
end

local function format_cell(value, column, where)
  value = lib.squash(value or '')
  if value == '' then return PLAIN and '—' or '\\reportmissing' end
  local fmt = column.fmt
  if fmt == 'raw' then
    return value -- already formatted (pivoted cells)
  elseif fmt == 'text' then
    return esc(value)
  elseif fmt == 'break' then
    return PLAIN and value or lib.breakable(value)
  elseif fmt == 'int' then
    return format_number(value, nil, where)
  elseif fmt:match('^num:%d+$') then
    return format_number(value, tonumber(fmt:match('%d+')), where)
  elseif fmt == 'bool' then
    if value == 'True' then return 'yes' end
    if value == 'False' then return 'no' end
    fail(where .. ': "' .. value .. '" is not True or False')
  elseif fmt == 'doi' or fmt == 'code' then
    if not lib.url_safe(value) then fail(where .. ': unsafe characters in "' .. value .. '"') end
    if PLAIN then return value end
    return (fmt == 'doi' and '\\reportdoi{' or '\\reportpath{') .. value .. '}'
  end
  fail(where .. ': unknown format "' .. tostring(fmt) .. '"')
end

------------------------------------------------------------------------------------------
-- Table assembly
------------------------------------------------------------------------------------------

local function column_spec(columns, where)
  local parts, total = { '@{}' }, 0
  local just = { l = '\\raggedright', r = '\\raggedleft', c = '\\centering' }
  for _, c in ipairs(columns) do
    total = total + c.width
    parts[#parts + 1] = string.format(
      '>{%s\\arraybackslash}p{\\dimexpr %.4f\\linewidth-2\\tabcolsep\\relax}',
      just[c.align] or fail(where .. ': bad alignment'), c.width)
  end
  if math.abs(total - 1) > 0.002 then
    fail(string.format('%s: column widths sum to %.3f, not 1', where, total))
  end
  parts[#parts + 1] = '@{}'
  return table.concat(parts)
end

local function header_row(columns)
  local cells = {}
  for _, c in ipairs(columns) do cells[#cells + 1] = '\\reporttablehead{' .. c.head .. '}' end
  return table.concat(cells, ' & ') .. ' \\\\'
end

local function group_value(spec, row, name)
  if spec.derived and spec.derived[name] then return spec.derived[name](row) end
  return row[name]
end

-- Rows as lists of formatted cells, with rules or gaps where a group changes.
local function body_lines(spec, columns, rows, where)
  local lines, previous = {}, nil
  for r, row in ipairs(rows) do
    if previous then
      if spec.rule_when and group_value(spec, row, spec.rule_when)
          ~= group_value(spec, previous, spec.rule_when) then
        lines[#lines + 1] = '\\midrule'
      elseif spec.space_when and row[spec.space_when] ~= previous[spec.space_when] then
        lines[#lines + 1] = '\\addlinespace[3pt]'
      end
    end
    local cells = {}
    for _, c in ipairs(columns) do
      if c['repeat'] == false and previous and row[c.field] == previous[c.field] then
        cells[#cells + 1] = ''
      else
        cells[#cells + 1] = format_cell(row[c.field], c,
          string.format('%s, row %d, column "%s"', where, r, c.field))
      end
    end
    lines[#lines + 1] = table.concat(cells, ' & ') .. ' \\\\'
    previous = row
  end
  return lines
end

local function longtable(opts)
  local n = #opts.columns
  local out = {}
  local function add(s) out[#out + 1] = s end
  if opts.landscape then add('\\begin{landscape}') end
  add('\\begin{ReportDataTable}{' .. opts.size .. '}')
  -- longtable steps the table counter when it starts, so the displayed number must be
  -- set before \begin{longtable} for \label and the List of Tables to carry it.
  if opts.prelude then add(opts.prelude) end
  add('\\begin{longtable}{' .. column_spec(opts.columns, opts.where) .. '}')
  add(opts.caption_line)
  add('\\toprule')
  add(header_row(opts.columns))
  add('\\midrule')
  add('\\endfirsthead')
  add(string.format('\\multicolumn{%d}{@{}l@{}}{\\reportcontinued{%s (continued)}}\\\\', n,
    opts.display))
  add('\\toprule')
  add(header_row(opts.columns))
  add('\\midrule')
  add('\\endhead')
  add('\\midrule')
  add(string.format('\\multicolumn{%d}{@{}r@{}}{\\reportcontinued{Continued on next page}}\\\\',
    n))
  add('\\endfoot')
  add('\\bottomrule')
  add('\\endlastfoot')
  for _, line in ipairs(opts.lines) do add(line) end
  add('\\end{longtable}')
  if opts.note ~= '' then add('\\reporttablenote{' .. opts.note .. '}') end
  add('\\end{ReportDataTable}')
  if opts.landscape then add('\\end{landscape}') end
  return table.concat(out, '\n')
end

------------------------------------------------------------------------------------------
-- Notes
------------------------------------------------------------------------------------------

local function constant_notes(spec, rows, where)
  local notes = {}
  for _, pair in ipairs(spec.constants or {}) do
    local field, label = pair[1], pair[2]
    local value
    for r, row in ipairs(rows) do
      if row[field] == nil then fail(where .. ': no column "' .. field .. '"') end
      local v = lib.squash(row[field])
      if value == nil then
        value = v
      elseif v ~= value then
        fail(string.format('%s: column "%s" is declared constant but row %d differs', where,
          field, r))
      end
    end
    notes[#notes + 1] = label .. ': ' .. esc(value or '') .. '.'
  end
  return notes
end

local function omitted_note(header, shown)
  local missing = {}
  for _, name in ipairs(header) do
    if not shown[name] then missing[#missing + 1] = path(name) end
  end
  if #missing == 0 then return nil end
  return 'Columns of the source file not shown here: ' .. table.concat(missing, ', ') .. '.'
end

local function check_columns(header, columns, where)
  local present = {}
  for _, name in ipairs(header) do present[name] = true end
  for _, c in ipairs(columns) do
    if not present[c.field] then fail(where .. ': CSV has no column "' .. c.field .. '"') end
  end
end

------------------------------------------------------------------------------------------
-- The within-tissue Spearman table is shown as tissue x model
------------------------------------------------------------------------------------------

local function pivot_rows(spec, header, rows, where)
  local p = spec.pivot
  for _, f in ipairs({ p.row_field, p.col_field, p.value_field, p.status_field, p.n_field,
    p.caveat_field }) do
    check_columns(header, { { field = f } }, where)
  end
  local order, by_key, omitted, undefined_status, caveat = {}, {}, {}, nil, nil
  for _, row in ipairs(rows) do
    local key, status = row[p.row_field], lib.squash(row[p.status_field])
    if status:sub(1, #p.omit_status_prefix) == p.omit_status_prefix then
      omitted[key] = status
    else
      if not by_key[key] then
        by_key[key] = { [p.row_field] = key, [p.n_field] = row[p.n_field] }
        order[#order + 1] = key
      elseif by_key[key][p.n_field] ~= row[p.n_field] then
        fail(where .. ': component count for ' .. key .. ' differs between models')
      end
      local cell
      if status:sub(1, #p.undefined_status_prefix) == p.undefined_status_prefix then
        cell = PLAIN and 'undefined' or p.undefined_text
        if undefined_status and undefined_status ~= status then
          fail(where .. ': more than one "undefined" status text')
        end
        undefined_status = status
      else
        cell = format_cell(row[p.value_field], { fmt = p.fmt }, where .. ', ' .. key)
        local c = lib.squash(row[p.caveat_field])
        if caveat and caveat ~= c then fail(where .. ': caveat text differs between rows') end
        caveat = c
      end
      by_key[key][row[p.col_field]] = cell
    end
  end
  local out = {}
  for _, key in ipairs(order) do
    local r = by_key[key]
    for _, m in ipairs(p.models) do
      if r[m] == nil then fail(where .. ': no value for model ' .. m .. ' in ' .. key) end
    end
    out[#out + 1] = r
  end
  local n_omitted = 0
  local omitted_status
  for _, s in pairs(omitted) do
    n_omitted = n_omitted + 1
    if omitted_status and omitted_status ~= s then fail(where .. ': mixed omission status') end
    omitted_status = s
  end
  local notes = {}
  if undefined_status then
    notes[#notes + 1] = (PLAIN and 'undefined' or '\\textit{undefined}') .. ': '
        .. esc(undefined_status) .. '.'
  end
  if caveat then notes[#notes + 1] = 'Defined values: ' .. esc(caveat) .. '.' end
  if n_omitted > 0 then
    notes[#notes + 1] = string.format('Not shown: %d tissues (%s).', n_omitted,
      esc(omitted_status))
  end
  return out, notes
end

------------------------------------------------------------------------------------------
-- Plain mode: pandoc tables for the DOCX edition (same columns, values and notes)
------------------------------------------------------------------------------------------

local ALIGN = { l = 'AlignLeft', r = 'AlignRight', c = 'AlignCenter' }

local function plain_blocks(display, caption_inl, panels, spec, rows, notes, where)
  local blocks = pandoc.List()
  for k, panel in ipairs(panels) do
    local cap = pandoc.List({
      pandoc.Strong(pandoc.Inlines(display .. (k > 1 and ' (continued).' or '.'))),
      pandoc.Space(),
    })
    if k == 1 then cap:extend(caption_inl) else cap:extend(pandoc.Inlines(panel.continuation)) end
    local aligns, widths, headers, body = {}, {}, {}, {}
    for _, c in ipairs(panel.columns) do
      aligns[#aligns + 1] = ALIGN[c.align]
      widths[#widths + 1] = c.width
      headers[#headers + 1] = { pandoc.Plain({ pandoc.Strong(pandoc.Inlines(c.head)) }) }
    end
    local previous
    for r, row in ipairs(rows) do
      local cells = {}
      for _, c in ipairs(panel.columns) do
        local text = ''
        if not (c['repeat'] == false and previous and row[c.field] == previous[c.field]) then
          text = format_cell(row[c.field], c,
            string.format('%s, row %d, column "%s"', where, r, c.field))
        end
        cells[#cells + 1] = { pandoc.Plain(pandoc.Inlines(text)) }
      end
      body[#body + 1] = cells
      previous = row
    end
    blocks:insert(pandoc.utils.from_simple_table(
      pandoc.SimpleTable(cap, aligns, widths, headers, body)))
  end
  local note = pandoc.List({ pandoc.Strong(pandoc.Inlines('Note.')), pandoc.Space() })
  note:extend(pandoc.Inlines(table.concat(notes, ' ')))
  blocks:insert(pandoc.Para(note))
  return blocks
end

------------------------------------------------------------------------------------------
-- One manifest entry
------------------------------------------------------------------------------------------

local function render(entry, spec, captions)
  local where = entry.report_label .. ' (' .. entry.path .. ')'
  if entry.status ~= 'generated' then
    fail(where .. ' has status "' .. entry.status .. '"; generate it before building')
  end
  local header, rows = lib.parse_csv(lib.read_file(entry.path), entry.path)
  local display = entry.report_label
  local number = display:gsub('^Table ', '')
  local label = lib.table_label(display)

  local caption_inl = spec.caption_key and captions[spec.caption_key]
  if spec.caption_key and not caption_inl then
    fail(where .. ': captions.md has no paragraph "' .. spec.caption_key .. '."')
  end
  caption_inl = caption_inl or pandoc.List({ pandoc.Str(entry.title .. '.') })
  local short = esc(entry.title)
  local caption = PLAIN and '' or to_latex(caption_inl)

  local notes = constant_notes(spec, rows, where)
  local shown = {}
  for _, pair in ipairs(spec.constants or {}) do shown[pair[1]] = true end

  local display_rows = rows
  if spec.pivot then
    local pivot_notes
    display_rows, pivot_notes = pivot_rows(spec, header, rows, where)
    for _, f in ipairs({ spec.pivot.row_field, spec.pivot.col_field, spec.pivot.value_field,
      spec.pivot.status_field, spec.pivot.n_field, spec.pivot.caveat_field }) do
      shown[f] = true
    end
    for _, n in ipairs(pivot_notes) do notes[#notes + 1] = n end
  elseif spec.keep then
    display_rows = {}
    for _, row in ipairs(rows) do
      if spec.keep(row) then display_rows[#display_rows + 1] = row end
    end
    notes[#notes + 1] = string.format(spec.row_note, #rows - #display_rows)
  end

  local panels = spec.panels or { spec }
  local any_number = false
  for _, panel in ipairs(panels) do
    if not spec.pivot then check_columns(header, panel.columns, where) end
    for _, c in ipairs(panel.columns) do
      shown[c.field] = true
      if c.fmt:match('^num:') or (spec.pivot and spec.pivot.fmt:match('^num:')) then
        any_number = true
      end
    end
  end
  if any_number then
    notes[#notes + 1] = 'Numbers are rounded for display to the decimals shown; the source '
        .. 'file holds full precision. A minus sign marks negative values.'
  end
  if spec.panels then
    notes[#notes + 1] = 'The table is printed in ' .. #panels .. ' parts that share the same '
        .. 'rows.'
  end
  local omitted = omitted_note(header, shown)
  if omitted then notes[#notes + 1] = omitted end
  notes[#notes + 1] = 'Source: ' .. path(entry.path) .. ', written by '
      .. path((entry.produced_by:gsub(' .*$', ''))) .. '.'

  if PLAIN then
    return plain_blocks(display, caption_inl, panels, spec, display_rows, notes, where),
        label, number
  end

  local blocks = {}
  for k, panel in ipairs(panels) do
    local caption_line, prelude
    if k == 1 then
      prelude = string.format('\\renewcommand{\\thetable}{%s}\\renewcommand{\\theHtable}{data.%s}',
        number, number)
      caption_line = string.format('\\caption[{%s}]{%s}\\label{%s}\\\\', short, caption, label)
    else
      prelude = string.format('\\renewcommand{\\theHtable}{data.%s.%d}', number, k)
      caption_line = string.format('\\caption*{\\reportcaptionlabel{%s (continued)}: %s}\\\\',
        display, panel.continuation or '')
    end
    blocks[#blocks + 1] = longtable({
      prelude = prelude,
      columns = panel.columns,
      size = panel.size or spec.size or '\\footnotesize',
      landscape = panel.landscape or spec.landscape,
      caption_line = caption_line,
      display = display,
      lines = body_lines(spec, panel.columns, display_rows, where),
      note = (k == #panels) and table.concat(notes, ' ') or '',
      where = where,
    })
  end
  return table.concat(blocks, '\n\n'), label, number
end

------------------------------------------------------------------------------------------
-- Entry point
------------------------------------------------------------------------------------------

-- Introduction of the DOCX appendix (the LaTeX edition has the same text in main.tex).
local PLAIN_INTRO = 'This appendix sets out the result tables listed in Appendix D, read '
    .. 'directly from the saved result files named in table_manifest.csv when the document '
    .. 'was built; no value was transcribed by hand. Each note states which columns and rows '
    .. 'are shown, how numbers were rounded for display, and the file the table was read from.'

function Pandoc(doc)
  local meta = doc.meta
  PLAIN = meta['table-format'] ~= nil and stringify(meta['table-format']) == 'plain'
  local manifest_path = meta_string(meta, 'table-manifest')
  local _, entries = lib.parse_csv(lib.read_file(manifest_path), manifest_path)
  local captions = load_captions(meta_string(meta, 'captions-file'))

  local out = {
    '% GENERATED by latex/filters/datatables.lua from table_manifest.csv and the CSV files',
    '% it lists. Do not edit: rerun latex/build.sh.',
  }
  local plain = pandoc.List({
    pandoc.Header(2, pandoc.Inlines('Appendix H — Result tables'),
      pandoc.Attr('appendix-h', { 'unnumbered' })),
    pandoc.Para(pandoc.Inlines(PLAIN_INTRO)),
  })
  if captions['Common notes'] then
    out[#out + 1] = '\\begin{ReportCommonNotes}' .. to_latex(captions['Common notes'])
        .. '\\end{ReportCommonNotes}'
    local para = pandoc.List({ pandoc.Strong(pandoc.Inlines(
      'Notes common to Tables 1–3 and S1–S4.')), pandoc.Space() })
    para:extend(captions['Common notes'])
    plain:insert(pandoc.Para(para))
  end

  local labels, sources, seen = {}, {}, {}
  for _, entry in ipairs(entries) do
    local spec = specs[entry.table_id]
    if not spec then
      fail('table_manifest.csv lists "' .. entry.table_id .. '" but table_specs.lua has no '
        .. 'layout for it')
    end
    seen[entry.table_id] = true
    local rendered, label, number = render(entry, spec, captions)
    if PLAIN then plain:extend(rendered) else out[#out + 1] = rendered end
    labels[#labels + 1] = label .. ' ' .. number
    sources[#sources + 1] = entry.path
  end
  for id in pairs(specs) do
    if not seen[id] then fail('table_specs.lua describes "' .. id .. '", absent from the manifest') end
  end
  if PLAIN then return pandoc.Pandoc(plain, pandoc.Meta({})) end

  -- every input of the report, for the provenance appendix
  local inputs = {
    meta_string(meta, 'report-source'), meta_string(meta, 'bib-file'),
    meta_string(meta, 'figure-manifest'), manifest_path, meta_string(meta, 'captions-file'),
  }
  local _, figures = lib.parse_csv(lib.read_file(meta_string(meta, 'figure-manifest')),
    'figure manifest')
  for _, f in ipairs(figures) do inputs[#inputs + 1] = f.pdf end
  for _, s in ipairs(sources) do inputs[#inputs + 1] = s end

  lib.write_file(meta_string(meta, 'labels-file'), table.concat(labels, '\n') .. '\n')
  lib.write_file(meta_string(meta, 'sources-file'), table.concat(inputs, '\n') .. '\n')

  return pandoc.Pandoc({ pandoc.RawBlock('latex', table.concat(out, '\n\n')) }, pandoc.Meta({}))
end
