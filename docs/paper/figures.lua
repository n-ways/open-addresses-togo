-- In the PDF a figure uses its vector PDF; the markdown on the web uses the SVG.
function Image(img)
  img.src = img.src:gsub('%.svg$', '.pdf')
  return img
end

-- Keep short tables on one page: ask for room for the whole table before it starts.
function Table(tbl)
  local rows = #tbl.head.rows
  for _, body in ipairs(tbl.bodies) do rows = rows + #body.body end
  if rows > 16 then return tbl end
  local lines = math.floor(rows * 1.6 + 4)
  return { pandoc.RawBlock('latex', '\\needspace{' .. lines .. '\\baselineskip}'), tbl }
end

-- An unnumbered section (Data and code availability, References) names itself in the running head,
-- instead of leaving the last numbered section there.
function Header(h)
  if h.level == 1 and h.classes:includes('unnumbered') then
    local title = pandoc.utils.stringify(h.content)
    return { h, pandoc.RawBlock('latex', '\\markboth{' .. title .. '}{}') }
  end
end
