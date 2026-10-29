-- report.lua: typeset reports/french_embassy/report.md as LaTeX fragments.
--
-- report.md is the single authoritative source of the report text. This filter never
-- changes wording; it only decides presentation:
--   * splits the document into the parts that main.tex inputs (report-part metadata):
--       metadata    -> \newcommand definitions for the cover page and PDF properties
--       summary     -> the unnumbered executive summary (front matter)
--       main        -> the numbered chapters, Introduction to Conclusion
--       appendices  -> Appendices A-G (the reference list is printed by biblatex)
--   * replaces each figure by a LaTeX float that uses the vector PDF named in
--     figure_manifest.csv, after checking that its number and caption match the manifest;
--   * turns textual references ("Figure 2a", "Table C3", "section 7") into hyperlinks,
--     failing if a reference has no target;
--   * gives Markdown tables content-based column widths and bold headers;
--   * typesets inline code as breakable monospaced paths.
-- It also writes the expected label -> number list that build.sh checks against the
-- final .aux file, so a numbering drift between Markdown and PDF stops the build.

PANDOC_VERSION:must_be_at_least '3.1'

local here = pandoc.path.directory(PANDOC_SCRIPT_FILE)
local lib = dofile(pandoc.path.join { here, 'lib.lua' })
local stringify = pandoc.utils.stringify
local fail = lib.fail

local MONTHS = { 'January', 'February', 'March', 'April', 'May', 'June', 'July',
  'August', 'September', 'October', 'November', 'December' }

local function meta_string(meta, key, default)
  local v = meta[key]
  if v == nil then
    if default == nil then fail('missing metadata "' .. key .. '" (passed by build.sh)') end
    return default
  end
  return stringify(v)
end

local function to_latex(inlines)
  local out = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), 'latex')
  return (out:gsub('%s+$', ''))
end

local function raw(text) return pandoc.RawBlock('latex', text) end
local function rawi(text) return pandoc.RawInline('latex', text) end

------------------------------------------------------------------------------------------
-- Manifests
------------------------------------------------------------------------------------------

local function load_figure_manifest(path)
  local _, rows = lib.parse_csv(lib.read_file(path), path)
  local by_png = {}
  for _, row in ipairs(rows) do
    for _, col in ipairs({ 'report_label', 'png', 'pdf', 'caption' }) do
      if (row[col] or '') == '' then fail(path .. ': empty "' .. col .. '" for a figure') end
    end
    by_png[row.png] = row
  end
  return rows, by_png
end

local function load_table_labels(path)
  local _, rows = lib.parse_csv(lib.read_file(path), path)
  local labels = {}
  for _, row in ipairs(rows) do
    labels[row.report_label] = lib.table_label(row.report_label)
  end
  return labels
end

------------------------------------------------------------------------------------------
-- Document structure
------------------------------------------------------------------------------------------

-- Split the top-level blocks into the named parts. Fails if the expected structure of
-- report.md (one executive summary, chapters, References, Appendices) is not found.
local function split_parts(blocks)
  local parts = { preamble = pandoc.List(), summary = pandoc.List(), main = pandoc.List(),
    references = pandoc.List(), appendices = pandoc.List() }
  local current = 'preamble'
  local chapters = {}
  for _, b in ipairs(blocks) do
    if b.t == 'Header' and b.level == 1 then
      local title = stringify(b.content)
      if title == 'Executive summary' then
        current = 'summary'
      elseif title == 'References' then
        current = 'references'
      elseif title == 'Appendices' then
        current = 'appendices'
      else
        if current == 'references' or current == 'appendices' then
          fail('unexpected chapter "' .. title .. '" after the References heading')
        end
        current = 'main'
        if b.classes:includes('unnumbered') then
          fail('chapter "' .. title .. '" is unnumbered; section references would drift')
        end
        chapters[#chapters + 1] = { id = b.identifier, title = title }
      end
    end
    parts[current]:insert(b)
  end
  for _, name in ipairs({ 'summary', 'main', 'references', 'appendices' }) do
    if #parts[name] == 0 then fail('report.md has no "' .. name .. '" part') end
  end
  return parts, chapters
end

------------------------------------------------------------------------------------------
-- Figures
------------------------------------------------------------------------------------------

local function figure_image(fig)
  local img
  fig:walk({ Image = function(i) img = i end })
  if not img then fail('a figure in report.md contains no image') end
  return img
end

-- Caption inlines with the leading bold "Figure N." removed; returns label and inlines.
local function split_caption(fig)
  local blocks = fig.caption.long
  if #blocks ~= 1 or not blocks[1].content then
    fail('figure caption is not a single paragraph')
  end
  local inl = pandoc.List(blocks[1].content)
  local first = inl[1]
  if not first or first.t ~= 'Strong' then
    fail('figure caption does not start with a bold "Figure N." label: '
      .. stringify(inl):sub(1, 60))
  end
  local label = stringify(first.content):gsub('%.$', '')
  inl:remove(1)
  while inl[1] and (inl[1].t == 'Space' or inl[1].t == 'SoftBreak') do inl:remove(1) end
  return label, inl
end

local ABBREVIATIONS = { ['e.g.'] = true, ['i.e.'] = true, ['vs.'] = true, ['et'] = true }

-- First sentence of a caption, for the List of Figures.
local function first_sentence(inl)
  local out = pandoc.List()
  for _, el in ipairs(inl) do
    out:insert(el)
    if el.t == 'Str' and el.text:match('%.$') and not ABBREVIATIONS[el.text] then
      break
    end
  end
  return out
end

-- Collect every figure in document order and check it against the manifest.
local function collect_figures(parts, manifest_rows, by_png)
  local figures, seen = {}, {}
  local expected = { main = 0, appendices = 0 }
  for _, part in ipairs({ 'preamble', 'summary', 'main', 'references', 'appendices' }) do
    pandoc.Pandoc(parts[part]):walk({
      Figure = function(fig)
        local img = figure_image(fig)
        local src = img.src:gsub('^%.%./%.%./', '')
        local row = by_png[src]
        if not row then fail('figure ' .. img.src .. ' is not in figure_manifest.csv') end
        local label, caption = split_caption(fig)
        if label ~= row.report_label then
          fail(string.format('%s is numbered "%s" in report.md but "%s" in the manifest',
            src, label, row.report_label))
        end
        if lib.fingerprint(stringify(caption)) ~= lib.fingerprint(row.caption) then
          fail(label .. ': caption in report.md differs from figure_manifest.csv; '
            .. 're-synchronise them before building')
        end
        -- LaTeX numbers main figures 1, 2, ... and appendix figures S1, S2, ... in order
        -- of appearance; the Markdown numbering must follow the same order.
        local supp, num = label:match('^Figure (S?)(%d+)$')
        local where = (supp == 'S') and 'appendices' or 'main'
        if part ~= where then
          fail(label .. ' must be in the ' .. where .. ' part, found in ' .. part)
        end
        expected[where] = expected[where] + 1
        if tonumber(num) ~= expected[where] then
          fail(label .. ' is out of order: LaTeX would number it '
            .. supp .. expected[where])
        end
        if seen[label] then fail(label .. ' appears twice in report.md') end
        seen[label] = true
        figures[#figures + 1] = { label = label, id = lib.figure_label(label), row = row }
      end,
    })
  end
  for _, row in ipairs(manifest_rows) do
    if not seen[row.report_label] then
      fail(row.report_label .. ' is in figure_manifest.csv but not in report.md')
    end
  end
  return figures
end

local function figure_block(fig, by_png)
  local img = figure_image(fig)
  local row = by_png[img.src:gsub('^%.%./%.%./', '')]
  local label, caption = split_caption(fig)
  -- Optional per-figure overrides in report.md: {latex-width=0.9 latex-height=0.5}
  -- (fractions of \linewidth and \textheight). Absent by default.
  local width = img.attributes['latex-width']
  local height = img.attributes['latex-height']
  local size = string.format('width=%s,height=%s,keepaspectratio',
    width and (width .. '\\linewidth') or '\\linewidth',
    height and (height .. '\\textheight') or '\\ReportFigureMaxHeight')
  return raw(table.concat({
    '\\begin{figure}[tbp]',
    '  \\centering',
    '  \\includegraphics[' .. size .. ']{' .. row.pdf .. '}',
    '  \\caption[{' .. to_latex(first_sentence(caption)) .. '}]{' .. to_latex(caption) .. '}',
    '  \\label{' .. lib.figure_label(label) .. '}',
    '\\end{figure}',
  }, '\n'))
end

------------------------------------------------------------------------------------------
-- Cross-references in running text
------------------------------------------------------------------------------------------

local function make_linker(fig_labels, tab_labels, chapters)
  local function target(kind, num)
    if kind:match('^Figure') then return fig_labels['Figure ' .. num] end
    return tab_labels['Table ' .. num]
  end

  -- "Figures 1 and 2 of that manuscript" refers to the source manuscript, not this report.
  local function about_source_manuscript(inl, i)
    local window = pandoc.List()
    for k = i, math.min(i + 12, #inl) do window:insert(inl[k]) end
    return stringify(window):find('of that manuscript', 1, true) ~= nil
  end

  local function number_pattern(kind)
    return kind:match('^Figure') and '^(S?%d+)(.*)$' or '^([CRS]?%d+)(.*)$'
  end

  local function link(kind, num)
    local t = target(kind, num)
    if not t then
      fail(string.format('"%s %s" in report.md has no matching %s', kind, num,
        kind:match('^Figure') and 'figure' or 'table in table_manifest.csv'))
    end
    return rawi('\\hyperref[' .. t .. ']{' .. kind .. '~' .. num .. '}')
  end

  local function section_links(str)
    local out = pandoc.List()
    local rest = str.text
    while true do
      local pre, num, post = rest:match('^(.-)§(%d+)(.*)$')
      if not num then break end
      local ch = chapters[tonumber(num)]
      if not ch then fail('"§' .. num .. '" in report.md has no matching chapter') end
      if pre ~= '' then out:insert(pandoc.Str(pre)) end
      out:insert(rawi('\\hyperref[' .. ch.id .. ']{§' .. num .. '}'))
      rest = post
    end
    if #out == 0 then return nil end
    if rest ~= '' then out:insert(pandoc.Str(rest)) end
    return out
  end

  return function(inl)
    local out = pandoc.List()
    local i = 1
    while i <= #inl do
      local el = inl[i]
      local consumed = false
      if el.t == 'Str' then
        local open, kind = el.text:match('^(%(?)(Figures?)$')
        if not kind then open, kind = el.text:match('^(%(?)(Tables?)$') end
        local nxt, numstr = inl[i + 1], inl[i + 2]
        if kind and nxt and nxt.t == 'Space' and numstr and numstr.t == 'Str'
            and not about_source_manuscript(inl, i) then
          local num, tail = numstr.text:match(number_pattern(kind))
          if num then
            if open ~= '' then out:insert(pandoc.Str(open)) end
            out:insert(link(kind, num))
            if tail ~= '' then out:insert(pandoc.Str(tail)) end
            i = i + 3
            consumed = true
            -- "Figures 8 and 9"
            if kind:match('s$') then
              local a, word, b, num2 = inl[i], inl[i + 1], inl[i + 2], inl[i + 3]
              if a and a.t == 'Space' and word and word.t == 'Str' and word.text == 'and'
                  and b and b.t == 'Space' and num2 and num2.t == 'Str' then
                local n2, tail2 = num2.text:match(number_pattern(kind))
                if n2 then
                  out:extend({ a, word, b, link(kind, n2) })
                  if tail2 ~= '' then out:insert(pandoc.Str(tail2)) end
                  i = i + 4
                end
              end
            end
          end
        end
        if not consumed and el.text:find('§', 1, true) then
          local replaced = section_links(el)
          if replaced then
            out:extend(replaced)
            i = i + 1
            consumed = true
          end
        end
      end
      if not consumed then
        out:insert(el)
        i = i + 1
      end
    end
    return out
  end
end

------------------------------------------------------------------------------------------
-- Inline code and long tokens
------------------------------------------------------------------------------------------

local function code_inline(c)
  if not lib.url_safe(c.text) then return nil end -- pandoc's own \texttt escaping
  local words = {}
  for w in c.text:gmatch('%S+') do words[#words + 1] = '\\reportpath{' .. w .. '}' end
  return rawi(table.concat(words, '\\ '))
end

-- Allow breaks inside long identifiers in narrow table cells (DOIs, archive IDs).
local function break_long_str(s)
  local len = utf8.len(s.text) or #s.text
  if len <= 18 or s.text:match('^[%d%.%-]+[,;%.]?$') or not s.text:find('[_/:%.%-]') then
    return nil
  end
  return rawi(lib.breakable(s.text))
end

------------------------------------------------------------------------------------------
-- Tables
------------------------------------------------------------------------------------------

local function cell_text_lengths(cell)
  local s = stringify(cell.contents)
  local longest_word = 0
  for w in s:gmatch('%S+') do longest_word = math.max(longest_word, utf8.len(w) or #w) end
  return utf8.len(s) or #s, longest_word
end

-- Content-based relative widths: pipe tables otherwise get equal widths.
local function set_widths(tbl)
  local ncol = #tbl.colspecs
  local maxlen, total, count, minw = {}, {}, {}, {}
  for j = 1, ncol do maxlen[j], total[j], count[j], minw[j] = 0, 0, 0, 3 end
  local function visit(row, is_head)
    for j, cell in ipairs(row.cells) do
      local len, word = cell_text_lengths(cell)
      minw[j] = math.max(minw[j], math.min(word, 24))
      if not is_head then
        maxlen[j] = math.max(maxlen[j], len)
        total[j] = total[j] + len
        count[j] = count[j] + 1
      end
    end
  end
  for _, row in ipairs(tbl.head.rows) do visit(row, true) end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do visit(row, false) end
  end
  local weights, sum = {}, 0
  for j = 1, ncol do
    local mean = count[j] > 0 and total[j] / count[j] or 0
    local w = math.max(0.35 * math.min(maxlen[j], 90) + 0.65 * mean, minw[j] + 1)
    weights[j] = w
    sum = sum + w
  end
  for j = 1, ncol do
    tbl.colspecs[j] = { tbl.colspecs[j][1], weights[j] / sum }
  end
end

local function bold_header(tbl)
  for _, row in ipairs(tbl.head.rows) do
    for _, cell in ipairs(row.cells) do
      cell.contents = cell.contents:walk({
        Plain = function(p)
          local inl = pandoc.List({ rawi('\\reporttablehead{') })
          inl:extend(p.content)
          inl:insert(rawi('}'))
          return pandoc.Plain(inl)
        end,
      })
    end
  end
end

local function table_blocks(tbl, cell_filter)
  if #tbl.caption.long == 0 then
    fail('a table in report.md has no caption ("Table: ..." line): '
      .. stringify(tbl.head):sub(1, 60))
  end
  set_widths(tbl)
  for _, row in ipairs(tbl.head.rows) do
    for _, cell in ipairs(row.cells) do cell.contents = cell.contents:walk(cell_filter) end
  end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      for _, cell in ipairs(row.cells) do cell.contents = cell.contents:walk(cell_filter) end
    end
  end
  bold_header(tbl)
  return { raw('\\begin{ReportInlineTable}'), tbl, raw('\\end{ReportInlineTable}') }
end

------------------------------------------------------------------------------------------
-- Parts
------------------------------------------------------------------------------------------

local function assert_top_level_only(blocks)
  for _, b in ipairs(blocks) do
    if b.t ~= 'Figure' and b.t ~= 'Table' then
      pandoc.Pandoc({ b }):walk({
        Figure = function() fail('figures must not be nested inside other blocks') end,
        Table = function() fail('tables must not be nested inside other blocks') end,
      })
    end
  end
end

local function transform(blocks, ctx)
  assert_top_level_only(blocks)
  local text_filter = { Inlines = ctx.linker, Code = code_inline }
  local cell_filter = { Inlines = ctx.linker, Code = code_inline, Str = break_long_str }
  local out = pandoc.List()
  for _, b in ipairs(blocks) do
    if b.t == 'RawBlock' and b.format == 'latex' and b.text:match('^\\newpage%s*$') then
      -- page breaks are decided by the LaTeX layout (chapters start on a new page)
    elseif b.t == 'RawBlock' and b.format == 'html' then
      -- HTML comments are notes for editors of report.md
    elseif b.t == 'Figure' then
      out:insert(figure_block(b, ctx.by_png))
    elseif b.t == 'Table' then
      out:extend(table_blocks(b, cell_filter))
    else
      out:insert(pandoc.Pandoc({ b }):walk(text_filter).blocks[1])
    end
  end
  return out
end

local function summary_part(blocks, ctx)
  local head = blocks[1]
  if not head.classes:includes('unnumbered') then
    fail('the Executive summary heading must carry {.unnumbered}, otherwise the pandoc '
      .. 'builds number it as chapter 1 and every "§N" reference in report.md shifts')
  end
  local out = pandoc.List({ raw('\\addchap{' .. to_latex(head.content) .. '}\\label{'
    .. head.identifier .. '}') })
  blocks:remove(1)
  out:extend(transform(blocks, ctx))
  return out
end

local function appendices_part(blocks, ctx)
  blocks:remove(1) -- the "Appendices" heading; main.tex opens the appendix chapter
  local expected = string.byte('A')
  local labels = {}
  for k, b in ipairs(blocks) do
    if b.t == 'Header' and b.level == 2 then
      local inl = pandoc.List(b.content)
      local dash
      for idx, el in ipairs(inl) do
        if el.t == 'Str' and el.text == '—' then
          dash = idx
          break
        end
      end
      local letter = stringify(inl):match('^Appendix (%u) —')
      if not dash or not letter then
        fail('appendix heading must read "Appendix X — Title": ' .. stringify(inl))
      end
      if letter ~= string.char(expected) then
        fail('appendix ' .. letter .. ' is out of order; expected '
          .. string.char(expected))
      end
      expected = expected + 1
      local title = pandoc.List()
      for idx = dash + 1, #inl do title:insert(inl[idx]) end
      while title[1] and title[1].t == 'Space' do title:remove(1) end
      local id = 'app-' .. letter:lower()
      labels[#labels + 1] = { id = id, number = letter }
      blocks[k] = pandoc.Header(2, title, pandoc.Attr(id))
    end
  end
  return transform(blocks, ctx), labels
end

local function metadata_part(meta)
  local title = pandoc.List(meta.title)
  local colon
  for idx, el in ipairs(title) do
    if el.t == 'Str' and el.text:match(':$') then
      colon = idx
      break
    end
  end
  if not colon then fail('the title in report.md is expected to read "Main: Subtitle"') end
  local main_title, sub_title = pandoc.List(), pandoc.List()
  for idx = 1, colon do main_title:insert(title[idx]) end
  main_title[colon] = pandoc.Str((title[colon].text:gsub(':$', '')))
  for idx = colon + 1, #title do sub_title:insert(title[idx]) end
  while sub_title[1] and sub_title[1].t == 'Space' do sub_title:remove(1) end

  local iso = meta_string(meta, 'date')
  local y, m, d = iso:match('^(%d%d%d%d)%-(%d%d)%-(%d%d)$')
  if not y then fail('date in report.md must be YYYY-MM-DD, found "' .. iso .. '"') end
  local date_long = string.format('%d %s %s', tonumber(d), MONTHS[tonumber(m)], y)

  local lines = {}
  local authors = meta.author or {}
  local kind = pandoc.utils.type(authors)
  if kind == 'Inlines' or kind == 'string' then authors = { authors } end
  for _, a in ipairs(authors) do
    local text = stringify(a)
    local role, value = text:match('^(.-):%s*(.*)$')
    if not role then role, value = '', text end
    local value_tex = lib.escape(value):gsub('%[TO BE COMPLETED%]',
      '\\ReportPlaceholder{TO BE COMPLETED}')
    lines[#lines + 1] = '\\ReportAuthorLine{' .. lib.escape(role) .. '}{' .. value_tex .. '}'
  end

  local plain = lib.escape(stringify(title))
  return pandoc.List({
    raw('% Generated from the YAML block of report.md by filters/report.lua. Do not edit.'),
    raw('\\newcommand{\\ReportTitleMain}{' .. to_latex(main_title) .. '}'),
    raw('\\newcommand{\\ReportTitleSub}{' .. to_latex(sub_title) .. '}'),
    raw('\\newcommand{\\ReportTitlePlain}{' .. plain .. '}'),
    raw('\\newcommand{\\ReportShortTitle}{' .. to_latex(main_title) .. '}'),
    raw('\\newcommand{\\ReportSubtitle}{' .. lib.escape(meta_string(meta, 'subtitle')) .. '}'),
    raw('\\newcommand{\\ReportDate}{' .. date_long .. '}'),
    raw('\\newcommand{\\ReportDateISO}{' .. iso .. '}'),
    raw('\\newcommand{\\ReportAuthors}{%\n' .. table.concat(lines, '%\n') .. '}'),
  })
end

local function write_expected_labels(path, figures, chapters, appendix_labels)
  local lines = {}
  for _, f in ipairs(figures) do
    lines[#lines + 1] = f.id .. ' ' .. f.label:gsub('^Figure ', '')
  end
  for n, ch in ipairs(chapters) do lines[#lines + 1] = ch.id .. ' ' .. n end
  for _, a in ipairs(appendix_labels) do lines[#lines + 1] = a.id .. ' ' .. a.number end
  lib.write_file(path, table.concat(lines, '\n') .. '\n')
end

------------------------------------------------------------------------------------------
-- Entry point
------------------------------------------------------------------------------------------

function Pandoc(doc)
  local part = meta_string(doc.meta, 'report-part')
  local manifest_rows, by_png = load_figure_manifest(meta_string(doc.meta, 'figure-manifest'))
  local tab_labels = load_table_labels(meta_string(doc.meta, 'table-manifest'))

  local parts, chapters = split_parts(doc.blocks)
  local figures = collect_figures(parts, manifest_rows, by_png)
  local fig_labels = {}
  for _, f in ipairs(figures) do fig_labels[f.label] = f.id end

  local ctx = { by_png = by_png, linker = make_linker(fig_labels, tab_labels, chapters) }

  local blocks
  if part == 'metadata' then
    blocks = metadata_part(doc.meta)
    local _, appendix_labels = appendices_part(parts.appendices:clone(), ctx)
    write_expected_labels(meta_string(doc.meta, 'labels-file'), figures, chapters,
      appendix_labels)
  elseif part == 'summary' then
    blocks = summary_part(parts.summary, ctx)
  elseif part == 'main' then
    blocks = transform(parts.main, ctx)
  elseif part == 'appendices' then
    blocks = appendices_part(parts.appendices, ctx)
  else
    fail('unknown report-part "' .. part .. '"')
  end

  local header = raw('% GENERATED from reports/french_embassy/report.md by '
    .. 'latex/filters/report.lua (part: ' .. part .. ').\n'
    .. '% Do not edit: change report.md and rerun latex/build.sh.')
  blocks:insert(1, header)
  return pandoc.Pandoc(blocks, pandoc.Meta({}))
end
