import './style.css'
import {
  marked
} from 'marked'
import DOMPurify from 'dompurify'
import {
  EditorView,
  basicSetup
} from 'codemirror'
import {
  StreamLanguage
} from '@codemirror/language'

const glyph = {
  logo: '<path d="M4 5.5h6v6H4zM14 12.5h6v6h-6zM10 8.5h7v4M7 11.5v4h7"/>',
  tree: '<path d="M4 5h4m-2 0v14m0-9h5m-5 5h5m-5 4h5M12 9h8m-8 5h8m-8 4h8"/>',
  diagram: '<rect x="3" y="3" width="7" height="5" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="8.5" y="16" width="7" height="5" rx="1"/><path d="M6.5 8v4h11V8M12 12v4"/>',
  trace: '<path d="m9 15 6-6m-8 8-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m7-1 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(2 2) scale(.83)"/>',
  file: '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6"/>',
  sections: '<path d="M4 5h16M4 10h16M4 15h10M4 20h10"/>',
  book: '<path d="M4 4h14v16H6a2 2 0 0 1-2-2zM4 16h14M8 8h6"/>',
  history: '<path d="M3 11a9 9 0 1 1 2.5 7M3 5v6h6m3-5v6l3 2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 3 3 3-2 3 1 2-3-1-3 2-2-2-3-3-1-1-3z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 5 5"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  board: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m6-16v16"/>',
  list: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18M9 4v16"/>',
  filter: '<path d="M4 6h16M7 12h10m-7 6h4"/><circle cx="8" cy="6" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  edit: '<path d="m5 16-1 4 4-1L20 7l-3-3zM14 7l3 3"/>',
  open: '<path d="M13 4h7v7m0-7-9 9m7 0v7H4V6h7"/>',
  warning: '<path d="M12 4 3 20h18zM12 10v4m0 3h.01"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4"/>',
  trash: '<path d="M4 6h16m-13 0 1 14h8l1-14M9 6V3h6v3"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
}

const icon = name => '<svg class="icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + (glyph[name] || '') + '</svg>'
const $ = (query, root = document) => root.querySelector(query)
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [c]))
const t = (ru, en) => state.locale === 'en' ? en : ru
const statuses = ['Draft', 'In Review', 'Approved', 'Implemented', 'Rejected']
const priorities = ['Must', 'Should', 'Could', "Won't"]
const types = ['BR', 'FR', 'NFR']
const kinds = ['sequence', 'class', 'activity', 'state', 'ER', 'component', 'use case', 'flowchart', 'other']
const linkTypes = ['depends_on', 'relates_to', 'conflicts_with']
const sectionLabels = {
  purpose: ['Цель и бизнес-контекст', 'Purpose and business context'],
  scope: ['Область применения', 'Scope'],
  stakeholders: ['Стейкхолдеры', 'Stakeholders'],
  business_goals: ['Бизнес-цели', 'Business goals'],
  assumptions: ['Допущения', 'Assumptions'],
  constraints: ['Ограничения', 'Constraints'],
  introduction: ['Введение', 'Introduction'],
  overview: ['Общее описание системы', 'System overview'],
  interfaces: ['Интерфейсы', 'Interfaces']
}
const state = {
  locale: localStorage.getItem('reqbase-locale') || 'ru',
  projectId: localStorage.getItem('reqbase-project'),
  projects: [],
  page: 'requirements',
  mode: 'tree',
  filters: {},
  showFilters: false,
  collapsed: new Set(),
  selection: new Set(),
  current: null,
  tab: 'details',
  rows: [],
  tree: [],
  diagrams: [],
  views: [],
  trace: {
    branches: [],
    orphans: []
  },
  gaps: {},
  details: {},
  quick: null,
  drag: null,
  loading: true,
  viewSequence: 0,
  detailSequence: 0
}
const pageLabels = () => ({
  requirements: ['tree', t('Требования', 'Requirements')],
  diagrams: ['diagram', t('Схемы', 'Diagrams')],
  trace: ['trace', t('Трассировка', 'Traceability')],
  documents: ['file', t('BRD и SRS', 'BRD and SRS')],
  sections: ['sections', t('Разделы документов', 'Document sections')],
  glossary: ['book', t('Глоссарий', 'Glossary')],
  exports: ['history', t('История выгрузок', 'Export history')],
  settings: ['gear', t('Настройки проекта', 'Project settings')],
  trash: ['trash', t('Корзина', 'Trash')]
})
const path = collection => '/projects/' + state.projectId + '/' + collection
const markdown = value => DOMPurify.sanitize(marked.parse(value || ''), {
  FORBID_TAGS: ['style', 'form', 'input', 'button'],
  FORBID_ATTR: ['style'],
  ALLOW_DATA_ATTR: false
})
const fmt = value => value ? new Date(value).toLocaleDateString(state.locale) : '—'
const slug = value => value.toLowerCase().replace(/[^a-z]+/g, '-').replace(/-$/, '')
const badge = (value, dot = false) => '<span class="badge ' + slug(value) + (dot ? ' dot' : '') + '">' + escape(value) + '</span>'
const button = (label, action, symbol = '', cls = '') => '<button type="button" class="' + cls + '" data-action="' + action + '">' + (symbol ? icon(symbol) : '') + escape(label) + '</button>'
const iconButton = (symbol, action, title) => '<button type="button" class="ghost icon-btn" data-action="' + action + '" title="' + escape(title) + '" aria-label="' + escape(title) + '">' + icon(symbol) + '</button>'
const options = (choices, value) => choices.map(item => {
  const [key, label] = Array.isArray(item) ? item : [item, item]
  return '<option value="' + escape(key) + '"' + (value === key ? ' selected' : '') + '>' + escape(label) + '</option>'
}).join('')
const field = (label, control) => '<label>' + escape(label) + control + '</label>'
const input = (name, value = '', attrs = '') => '<input name="' + name + '" value="' + escape(value) + '" ' + attrs + '>'
const textarea = (name, value = '') => '<textarea name="' + name + '">' + escape(value) + '</textarea>'
const select = (name, choices, value, attrs = '') => '<select name="' + name + '" ' + attrs + '>' + options(choices, value) + '</select>'
const removeEmpty = object => Object.fromEntries(Object.entries(object).filter(([, v]) => v !== '' && v != null))
const formData = form => Object.fromEntries(new FormData(form))
const rowById = id => state.rows.find(row => row.id === id)
const heading = (title, text, actions = '') => '<header class="page-head"><div><h1>' + escape(title) + '</h1><p>' + escape(text) + '</p></div><div class="flex">' + actions + '</div></header>'
const empty = (title, detail = '', action = '') => '<div class="empty"><strong>' + escape(title) + '</strong>' + escape(detail) + (action ? '<p>' + action + '</p>' : '') + '</div>'
const footer = (label = t('Сохранить', 'Save')) => '<div class="form-footer">' + button(t('Отмена', 'Cancel'), 'close-modal') + '<button class="primary" type="submit">' + escape(label) + '</button></div>'

async function request(url, method = 'GET', body, responseType = 'json') {
  const response = await fetch('/ui' + url, {
    method,
    headers: {
      'X-ReqBase-UI': '1',
      ...(body === undefined ? {} : {
        'Content-Type': 'application/json'
      })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const error = new Error(data.message || (Array.isArray(data.detail) ? data.detail.map(item => item.loc.join('.') + ' · ' + item.msg).join('\n') : data.detail) || response.statusText)
    error.status = response.status
    throw error
  }
  return responseType === 'blob' ? response.blob() : response.json()
}

function toast(message, error = false) {
  const item = document.createElement('div')
  item.className = 'toast' + (error ? ' error' : '')
  item.textContent = message
  $('#toasts').append(item)
  setTimeout(() => item.remove(), error ? 6500 : 2800)
}

async function run(work) {
  try {
    return await work()
  } catch (error) {
    if (error.status === 409) toast(t('Конфликт версий. Обновлены данные в рабочей области.', 'Version conflict. Workspace data has been refreshed.'), true)
    else toast(error.message, true)
    if (error.status === 409) await refresh().catch(() => {})
  }
}

async function download(url, filename) {
  const blob = await request(url, 'GET', undefined, 'blob')
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(href), 2000)
}

async function boot() {
  state.projects = await request('/projects')
  const stored = state.projects.find(project => project.id === state.projectId)
  state.projectId = (stored || state.projects[0])?.id || null
  await refresh(true)
}

function query() {
  return new URLSearchParams(removeEmpty(state.filters)).toString()
}

async function refresh(selectInitial = false) {
  const seq = ++state.viewSequence
  if (!state.projectId) {
    state.loading = false
    render()
    return
  }
  const [rows, tree, diagrams, views, trace, gaps] = await Promise.all([
    request(path('requirements')), request(path('tree') + '?' + query()),
    request(path('diagrams')), request(path('views')), request(path('traceability')), request(path('gaps'))
  ])
  if (seq !== state.viewSequence) return
  Object.assign(state, {
    rows,
    tree,
    diagrams,
    views,
    trace,
    gaps,
    loading: false
  })
  if (selectInitial && matchMedia('(min-width: 901px)').matches) {
    const candidate = rows.find(row => row.description && row.type === 'FR')
    state.current = candidate?.id || null
  }
  if (state.current && !rowById(state.current)) state.current = null
  if (state.current) await detailData(state.current)
  if (seq === state.viewSequence) render()
}

async function detailData(id) {
  const seq = ++state.detailSequence
  const query = '?requirement_id=' + encodeURIComponent(id)
  const [attachments, comments, links, history] = await Promise.all([
    request(path('requirement-diagrams') + query), request(path('comments') + query),
    request(path('links') + query), request('/requirements/' + id + '/history')
  ])
  if (seq === state.detailSequence && state.current === id) state.details = {
    attachments,
    comments,
    links,
    history
  }
}

async function selectRow(id) {
  state.current = id
  state.tab = 'details'
  state.details = {}
  if (!$('.work-area')) render()
  else renderInspector()
  await detailData(id)
  if (state.current === id) renderInspector()
}

function renderInspector() {
  const area = $('.work-area')
  const row = rowById(state.current)
  if (!area || !row) return
  area.classList.add('with-detail')
  for (const element of area.querySelectorAll('tr[data-row]')) {
    const selected = element.dataset.row === row.id
    element.classList.toggle('selected', selected)
    element.setAttribute('aria-selected', String(selected))
  }
  const existing = $('.inspector', area)
  if (existing) existing.outerHTML = inspector(row)
  else area.insertAdjacentHTML('beforeend', inspector(row))
  hydrateThumbnails()
}

function nav() {
  const labels = pageLabels()
  const navButton = id => '<button class="' + (state.page === id ? 'active' : '') + '" data-action="page:' + id + '">' + icon(labels[id][0]) + escape(labels[id][1]) +
    (id === 'requirements' && state.rows.length ? '<span class="nav-count">' + state.rows.length + '</span>' : '') + '</button>'
  const project = state.projects.find(item => item.id === state.projectId)
  return '<aside class="sidebar"><div class="brand"><div class="brand-icon">' + icon('logo') + '</div><span class="brand-text">Req<b>Base</b></span></div>' +
    '<button class="project-control" data-action="projects"><span class="project-symbol">' + escape(project?.prefix.slice(0, 2) || 'RB') + '</span><span class="grow ellipsis"><strong>' + escape(project?.title || t('Выбрать проект', 'Choose project')) + '</strong><small>' + escape(project?.prefix || 'ReqBase') + '</small></span>' + icon('down') + '</button>' +
    '<div class="side-heading">' + t('Рабочее пространство', 'Workspace') + '</div><nav class="nav">' + ['requirements', 'diagrams', 'trace'].map(navButton).join('') + '</nav>' +
    '<div class="side-heading">' + t('Документация', 'Documentation') + '</div><nav class="nav">' + ['documents', 'sections', 'glossary', 'exports'].map(navButton).join('') + '</nav>' +
    '<div class="side-bottom"><nav class="nav">' + ['settings', 'trash'].map(navButton).join('') + '</nav><div class="side-footer"><div class="flex"><span class="avatar">A</span><span><strong>' + t('Аналитик', 'Analyst') + '</strong><small>' + t('Локальное пространство', 'Local workspace') + '</small></span></div>' + button(state.locale.toUpperCase(), 'locale', '', 'locale') + '</div></div></aside>'
}

function render() {
  document.documentElement.lang = state.locale
  const activeInput = document.activeElement
  const where = activeInput?.id
  const cursor = activeInput?.type === 'search' ? activeInput.selectionStart : null
  const selected = state.projects.find(project => project.id === state.projectId)
  const label = pageLabels()[state.page][1]
  $('#app').innerHTML = '<div class="app-shell">' + nav() + '<div class="workspace"><header class="topbar"><div class="breadcrumb"><span class="mobile-nav">' +
    iconButton('menu', 'mobile-nav', t('Навигация', 'Navigation')) + '</span><span class="project-crumb">' + escape(selected?.title || 'ReqBase') + '</span><span class="crumb-chevron">' + icon('right') + '</span><strong>' + escape(label) + '</strong></div>' +
    '<div class="flex"><label class="search">' + icon('search') + '<input id="global-search" type="search" placeholder="' + t('Поиск требований…', 'Search requirements…') + '" value="' + escape(state.filters.q || '') + '" aria-label="' + t('Поиск требований', 'Search requirements') + '"><kbd>/</kbd></label>' +
    iconButton('history', 'refresh', t('Обновить данные', 'Refresh data')) + '</div></header><main class="main">' + page() + '</main></div></div>'
  if (where && document.getElementById(where)) {
    const element = document.getElementById(where)
    element.focus({
      preventScroll: true
    })
    if (cursor !== null) {
      try {
        element.setSelectionRange(cursor, cursor)
      } catch {}
    }
  }
  if (state.quick && $('#quick-title')) $('#quick-title').focus({
    preventScroll: true
  })
  hydrateThumbnails()
}

function page() {
  if (state.loading) return '<div class="loading">' + t('Загрузка проекта…', 'Loading project…') + '</div>'
  if (!state.projectId && state.page === 'trash') return trashPage()
  if (!state.projectId) return heading('ReqBase', t('База требований', 'Requirements workspace')) +
    '<div class="panel">' + empty(t('Создайте проект', 'Create a project'), t('Требования, схемы и документы проекта будут связаны между собой.', 'Keep requirements, diagrams and project documents connected.'), button(t('Создать проект', 'Create project'), 'new-project', 'plus', 'primary') + ' ' + button(t('Импортировать резервную копию', 'Import backup'), 'restore-backup', 'upload') + ' ' + button(t('Корзина', 'Trash'), 'page:trash', 'trash')) + '</div>'
  return ({
    requirements: requirementsPage,
    diagrams: diagramsPage,
    trace: tracePage,
    documents: documentsPage,
    sections: sectionsPage,
    glossary: glossaryPage,
    exports: exportsPage,
    settings: settingsPage,
    trash: trashPage
  })[state.page]()
}

function stat(symbol, color, value, label) {
  return '<div class="stat"><span class="stat-icon ' + color + '">' + icon(symbol) + '</span><div><strong>' + value + '</strong><span>' + escape(label) + '</span></div></div>'
}

function requirementsPage() {
  const stats = [
    stat('tree', '', state.rows.length, t('Всего требований', 'Total requirements')),
    stat('check', 'blue', state.rows.filter(row => row.status === 'Approved').length, t('Утверждено', 'Approved')),
    stat('warning', 'amber', state.gaps.br_without_fr?.length || 0, t('BR без покрытия', 'BR without coverage')),
    stat('diagram', 'purple', state.diagrams.length, t('Схемы проекта', 'Project diagrams'))
  ]
  const title = heading(t('Требования', 'Requirements'), t('Матрица бизнес-, функциональных и нефункциональных требований', 'Business, functional and non-functional requirements matrix'),
    button(t('Импорт', 'Import'), 'import', 'upload') + button(t('Новое требование', 'New requirement'), 'new-req', 'plus', 'primary'))
  const selected = rowById(state.current)
  return title + '<div class="stats">' + stats.join('') + '</div><div class="work-area' + (selected ? ' with-detail' : '') + '">' +
    '<section class="panel matrix">' + toolbar() + (state.mode === 'kanban' ? kanban() : table()) + '</section>' +
    (selected ? inspector(selected) : '') + '</div>'
}

function toolbar() {
  const modes = [
    ['tree', 'tree', t('Дерево', 'Tree')],
    ['flat', 'list', t('Таблица', 'Table')],
    ['kanban', 'board', t('Канбан', 'Kanban')]
  ]
  const view = '<div class="segmented">' + modes.map(([mode, symbol, label]) => button(label, 'mode:' + mode, symbol, state.mode === mode ? 'active' : '')).join('') + '</div>'
  const filterCount = Object.keys(removeEmpty(state.filters)).filter(key => key !== 'q').length
  const controls = button(t('Фильтры', 'Filters') + (filterCount ? ' · ' + filterCount : ''), 'filters', 'filter') +
    button(t('Виды', 'Views'), 'views', 'book') + (state.mode === 'tree' ? iconButton('more', 'grid-menu', t('Действия с деревом', 'Tree actions')) : '')
  const bulk = state.selection.size ? '<div class="filterbar">' + button(t('Изменить выбранные', 'Edit selected') + ' · ' + state.selection.size, 'bulk', 'edit', 'primary') + button(t('Снять выбор', 'Clear selection'), 'clear-selection') + '</div>' : ''
  const lists = [
    ['type', t('Тип', 'Type'), types],
    ['status', t('Статус', 'Status'), statuses],
    ['priority', t('Приоритет', 'Priority'), priorities],
    ['tag', t('Тег', 'Tag'), [...new Set(state.rows.flatMap(row => row.tags))]],
    ['updated_by', t('Автор правки', 'Updated by'), [...new Set(state.rows.map(row => row.updated_by))]],
    ['has_diagrams', t('Схемы', 'Diagrams'), [
      ['true', t('Со схемами', 'With diagrams')],
      ['false', t('Без схем', 'Without diagrams')]
    ]]
  ]
  const filters = state.showFilters ? '<div class="filterbar">' + lists.map(([key, label, values]) =>
      select(key, [
        ['', label], ...values
      ], String(state.filters[key] ?? ''), 'data-filter aria-label="' + escape(label) + '"')).join('') +
    button(t('Сбросить', 'Reset'), 'reset-filters', '', 'small') + '</div>' : ''
  return '<div class="toolbar">' + view + '<div class="flex">' + controls + '</div></div>' + filters + bulk
}

function flatten(nodes, level = 0, respectCollapse = false) {
  return nodes.flatMap(node => [{
      node,
      level
    },
    ...((respectCollapse && state.collapsed.has(node.id)) ? [] : flatten(node.children, level + 1, respectCollapse))
  ])
}

function table() {
  const items = flatten(state.tree, 0, state.mode === 'tree').filter(({
    node
  }) => state.mode === 'tree' || node.matches)
  const titles = [t('Код', 'Code'), t('Название требования', 'Requirement title'), t('Тип', 'Type'), t('Статус', 'Status'), t('Приоритет', 'Priority'), t('Схемы', 'Diagrams'), t('Теги', 'Tags')]
  let lines = items.map(({
    node,
    level
  }) => rowMarkup(node, state.mode === 'tree' ? level : 0)).join('')
  if (state.quick && !items.some(({
      node
    }) => node.id === state.quick.anchor)) lines += quickRow()
  return '<div class="grid-scroll"><table class="grid" aria-label="' + t('Матрица требований', 'Requirements matrix') + '"><thead><tr><th><input id="select-all" type="checkbox" aria-label="' +
    t('Выбрать видимые', 'Select visible') + '"' + (items.length && items.every(({
      node
    }) => state.selection.has(node.id)) ? ' checked' : '') + '></th>' + titles.map(title => '<th>' + title + '</th>').join('') +
    '</tr></thead><tbody>' + lines + '</tbody></table>' +
    (!items.length && !state.quick ? empty(t('Требования не найдены', 'No requirements found'), t('Создайте требование или измените фильтры.', 'Create a requirement or adjust the filters.')) : '') +
    '</div><div class="grid-footer"><span>' + t('Показано', 'Showing') + ' ' + items.length + ' ' + t('из', 'of') + ' ' + state.rows.length + '</span><span><kbd>Enter</kbd> ' +
    t('добавить', 'add') + ' &nbsp; <kbd>Tab</kbd> ' + t('вложить', 'nest') + '</span></div>'
}

function rowMarkup(row, level) {
  const indent = Math.min(level * 10, 38)
  const branch = state.mode === 'tree' && row.children.length
  const rowClass = [row.id === state.current ? 'selected' : '', row.matches ? '' : 'dim'].join(' ')
  const status = '<button class="badge control dot ' + slug(row.status) + '" data-action="inline:status:' + row.id + '">' + escape(row.status) + '</button>'
  const priority = '<button class="badge control ' + slug(row.priority) + '" data-action="inline:priority:' + row.id + '">' + escape(row.priority) + '</button>'
  return '<tr class="' + rowClass + '" data-row="' + row.id + '" draggable="true" tabindex="0" aria-selected="' + (row.id === state.current) + '">' +
    '<td><input type="checkbox" data-pick="' + row.id + '" aria-label="' + escape(row.code) + '"' + (state.selection.has(row.id) ? ' checked' : '') + '></td><td><div class="code-cell" style="padding-left:' + indent + 'px">' +
    (branch ? iconButton(state.collapsed.has(row.id) ? 'right' : 'down', 'fold:' + row.id, t('Свернуть или развернуть', 'Toggle branch')) : '<span class="route-spacer">' + (level ? '└' : '') + '</span>') +
    '<span class="code" title="' + escape(row.code) + '">' + escape(row.code) + '</span></div></td><td class="title-cell"><button class="title-control" title="' + escape(row.title) + '" data-action="row:' + row.id + '">' +
    escape(row.title) + '</button></td><td>' + badge(row.type) + '</td><td>' + status + '</td><td>' + priority + '</td><td><span class="diagram-number">' +
    (row.diagram_count ? icon('diagram') + ' ' + row.diagram_count : '—') + '</span></td><td><div class="tag-list">' +
    row.tags.map(tag => '<span class="badge tag" title="' + escape(tag) + '">' + escape(tag) + '</span>').join('') + '</div></td></tr>' +
    (state.quick?.anchor === row.id ? quickRow() : '')
}

function quickRow() {
  const node = rowById(state.quick.parent)
  return '<tr class="quick-row"><td></td><td>' + badge(node ? 'FR' : 'BR') + '</td><td colspan="6"><input id="quick-title" placeholder="' +
    t('Название · Enter сохранить · Esc отменить', 'Title · Enter to save · Esc to cancel') + '" value="' + escape(state.quick.title) + '"></td></tr>'
}

function kanban() {
  const rows = flatten(state.tree).map(({
    node
  }) => node).filter(row => row.matches)

  return '<div class="kanban">' + statuses.map(status => '<section class="lane" data-lane="' + status + '">' + badge(status, true) +
    ' <span class="muted">' + rows.filter(row => row.status === status).length + '</span>' +
    rows.filter(row => row.status === status).map(row => '<article tabindex="0" class="tile" data-row="' + row.id +

      '" draggable="true"><span class="muted">' + row.code + '</span><strong>' + escape(row.title) + '</strong>' + badge(row.priority) + '</article>').join('') + '</section>').join('') + '</div>'
}

function inspector(row) {
  const tabs = [
    ['details', t('Описание', 'Details')],
    ['diagrams', t('Схемы', 'Diagrams')],
    ['comments', t('Комментарии', 'Comments')],
    ['links', t('Связи', 'Links')],
    ['history', t('История', 'History')]
  ]
  const content = {
    details: () => '<section><h3>' + t('Описание', 'Description') + '</h3><div class="markdown">' + (row.description ? markdown(row.description) : '—') +
      '</div></section><section><h3>' + t('Критерии приёмки', 'Acceptance criteria') + '</h3><ul class="criteria">' + (row.acceptance_criteria.map(text => '<li>' + icon('check') + escape(text) + '</li>').join('') || '<li>—</li>') +
      '</ul></section>' + (row.source ? '<section><h3>' + t('Источник', 'Source') + '</h3><div class="muted">' + escape(row.source) + '</div></section>' : '') +
      (row.diagram_count ? '<section><h3>' + t('Прикреплённые схемы', 'Attached diagrams') + '</h3>' + attachments(false) + '</section>' : ''),
    diagrams: () => '<div class="stack">' + attachments(true) + '<div class="flex">' + button(t('Прикрепить', 'Attach'), 'attach', 'trace') + button(t('Создать', 'Create'), 'diagram:new:attached', 'plus') + '</div></div>',
    comments: () => '<div class="stack">' + (state.details.comments || []).map(item => '<div class="sheet-row"><div class="grow"><b>' + escape(item.created_by) + '</b><span class="muted"> · ' +
        fmt(item.created_at) + '</span><div class="markdown">' + markdown(item.body) + '</div></div>' + iconButton('edit', 'comment-edit:' + item.id, t('Править', 'Edit')) +
        iconButton('trash', 'item-delete:comments:' + item.id, t('Удалить', 'Delete')) + '</div>').join('') + '<form class="form" id="comment-form">' +
      field(t('Комментарий', 'Comment'), textarea('body')) + '<button class="primary">' + t('Отправить', 'Post') + '</button></form></div>',
    links: () => '<div class="stack">' + (state.details.links || []).map(link => {
      const related = rowById(link.source_id === row.id ? link.target_id : link.source_id)
      return related ? '<div class="sheet-row"><div class="grow"><b>' + escape(link.type) + '</b><br>' + requirementButton(related) + '</div>' +
        iconButton('trash', 'item-delete:links:' + link.id, t('Удалить связь', 'Remove link')) + '</div>' : ''
    }).join('') + button(t('Добавить связь', 'Add link'), 'link', 'trace') + '</div>',
    history: () => (state.details.history || []).slice().reverse().map(item => '<details><summary>' + escape(item.action) + ' · ' +
      escape(item.actor) + ' · ' + escape(item.channel) + ' · ' + fmt(item.created_at) + '</summary><pre>' + escape(JSON.stringify(item.diff, null, 2)) + '</pre>' +
      button(t('Вернуть состояние до правки', 'Rollback this change'), 'rollback:' + item.id, 'history', 'small') + '</details>').join('') || '<span class="muted">—</span>'
  }
  return '<aside class="panel inspector"><div class="inspector-head"><div class="flex between"><div class="flex"><span class="code">' + row.code + '</span>' + badge(row.type) +
    '</div><div class="flex">' + iconButton('more', 'row-menu:' + row.id, t('Действия', 'Actions')) + iconButton('x', 'close-row', t('Закрыть', 'Close')) + '</div></div><h2>' + escape(row.title) +
    '</h2><div class="flex">' + badge(row.status, true) + badge(row.priority) + '</div></div><div class="inspector-tabs">' +
    tabs.map(([tab, label]) => button(label, 'tab:' + tab, '', state.tab === tab ? 'active' : '')).join('') + '</div><div class="inspector-body">' + content[state.tab]() +
    '</div><div class="detail-meta"><span>' + t('Изменено', 'Updated') + ' · ' + fmt(row.updated_at) + '</span><span>' + escape(row.updated_by) + ' · v' + row.version + '</span></div></aside>'
}

function attachments(edit) {
  return (state.details.attachments || []).map(link => {
    const item = state.diagrams.find(diagram => diagram.id === link.diagram_id)
    return item ? '<div class="stack">' + thumbnail(item) + '<div class="flex between">' +
      button(item.title, 'full:' + item.id, 'open', 'small') + (edit ? iconButton('trash', 'item-delete:requirement-diagrams:' + link.id, t('Открепить', 'Detach')) : '') +
      '</div></div>' : ''
  }).join('') || (edit ? '<p class="muted">' + t('Схемы ещё не прикреплены', 'No diagrams attached') + '</p>' : '')
}

const thumbnail = item => '<button class="thumb" data-thumb="' + item.id + '" data-action="full:' + item.id + '" aria-label="' + escape(item.title) + '">' + icon('diagram') + '</button>'
const thumbs = new Map()
let mermaidModule
async function drawMermaid(source) {
  if (!mermaidModule) {
    mermaidModule = import('mermaid').then(({
      default: mermaid
    }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'neutral',
        suppressErrorRendering: true
      })
      return mermaid
    })
  }
  const mermaid = await mermaidModule
  const result = await mermaid.render('req-diagram-' + crypto.randomUUID(), source)
  return new Blob([result.svg], {
    type: 'image/svg+xml'
  })
}

function thumbUrl(item) {
  const cached = thumbs.get(item.id)
  if (cached?.version === item.version) return cached.promise
  if (cached) cached.promise.then(URL.revokeObjectURL).catch(() => {})
  const promise = (item.type === 'mermaid' ? drawMermaid(item.source) :
    request('/diagrams/' + item.id + '/render', 'GET', undefined, 'blob')).then(blob => URL.createObjectURL(blob))
  thumbs.set(item.id, {
    version: item.version,
    promise
  })
  promise.catch(() => {
    if (thumbs.get(item.id)?.promise === promise) thumbs.delete(item.id)
  })
  return promise
}

function hydrateThumbnails() {
  document.querySelectorAll('[data-thumb]').forEach(element => {
    const item = state.diagrams.find(diagram => diagram.id === element.dataset.thumb)
    if (item) thumbUrl(item).then(url => {
      if (element.isConnected) element.innerHTML = '<img alt="' + escape(item.title) + '" src="' + url + '">'
    }).catch(() => {})
  })
}

function diagramsPage() {
  const cards = state.diagrams.map(item => '<article class="panel card">' + thumbnail(item) + '<div class="flex">' + badge(item.type) + ' <span class="muted">' +
    escape(item.kind) + '</span></div><h3>' + escape(item.title) + '</h3><div class="flex">' +
    button(t('Открыть редактор', 'Open editor'), 'diagram:' + item.id, 'edit', 'small') + iconButton('more', 'diagram-menu:' + item.id, t('Действия', 'Actions')) + '</div></article>').join('')
  return heading(t('Схемы', 'Diagrams'), t('Библиотека диаграмм проекта', 'Project diagram library'), button(t('Новая схема', 'New diagram'), 'diagram:new', 'plus', 'primary')) +
    (cards ? '<div class="cards">' + cards + '</div>' : '<div class="panel">' + empty(t('Схем пока нет', 'No diagrams yet'), '',
      button(t('Создать схему', 'Create diagram'), 'diagram:new', 'plus', 'primary')) + '</div>')
}

const requirementButton = row => button(row.code + ' · ' + row.title, 'jump:' + row.id, '', 'small')

function tracePage() {
  const labels = {
    br_without_fr: t('BR без функциональных требований', 'BR without functional requirements'),
    fr_without_br: t('FR без родительского BR', 'FR without a parent BR'),
    without_acceptance_criteria: t('Без критериев приёмки', 'Missing acceptance criteria'),
    br_without_diagrams: t('BR без схем', 'BR without diagrams'),
    must_draft: t('Must в статусе Draft', 'Draft Must requirements')
  }
  const rows = state.trace.branches.map(({
      br,
      fr,
      nfr
    }) => '<tr' + (fr.length ? '' : ' class="warn"') + '><td>' + requirementButton(br) +
    '</td><td>' + (fr.map(requirementButton).join('') || '—') + '</td><td>' + (nfr.map(requirementButton).join('') || '—') + '</td></tr>').join('')
  const orphans = state.trace.orphans.map(row => '<tr class="warn"><td>—</td><td>' + (row.type === 'FR' ? requirementButton(row) : '—') +
    '</td><td>' + (row.type === 'NFR' ? requirementButton(row) : '—') + '</td></tr>').join('')
  return heading(t('Трассировка', 'Traceability'), t('Покрытие бизнес-требований и пробелы в базе', 'Business requirement coverage and gaps')) +
    '<div class="stack"><section class="panel grid-scroll"><table class="trace"><thead><tr><th>BR</th><th>FR</th><th>NFR</th></tr></thead><tbody>' + rows + orphans +
    '</tbody></table></section><div class="cards">' + Object.entries(labels).map(([key, label]) => '<section class="panel card gap-block"><h3>' +
      escape(label) + ' · ' + (state.gaps[key]?.length || 0) + '</h3>' + (state.gaps[key] || []).map(requirementButton).join(' ') + '</section>').join('') + '</div></div>'
}

function documentsPage() {
  return heading(t('BRD и SRS', 'BRD and SRS'), t('Формирование документов из базы требований проекта', 'Generate documents from project requirements')) +
    '<div class="cards">' + [
      ['BRD', t('Документ бизнес-требований', 'Business requirements document')],
      ['SRS', t('Спецификация требований к системе', 'System requirements specification')]
    ].map(([id, title]) =>
      '<article class="panel card"><span class="stat-icon">' + icon('file') + '</span><h3>' + id + '</h3><p>' + escape(title) + '</p>' +
      button(t('Сформировать', 'Generate') + ' ' + id, 'document:' + id, 'file', 'primary') + '</article>').join('') + '</div>'
}

function sectionsPage() {
  return heading(t('Разделы документов', 'Document sections'), t('Текстовые разделы BRD и SRS в Markdown', 'Markdown sections shared by BRD and SRS')) +
    '<div class="panel sheet">' + Object.entries(sectionLabels).map(([key, labels]) => {
      const item = (state.extra || []).find(section => section.key === key)
      return '<div class="sheet-row"><div class="grow ellipsis"><strong>' + escape(t(...labels)) + '</strong><p class="muted ellipsis">' +
        escape(item?.body || '—') + '</p></div>' + iconButton('edit', 'section:' + key, t('Редактировать', 'Edit')) + '</div>'
    }).join('') + '</div>'
}

function glossaryPage() {
  return heading(t('Глоссарий', 'Glossary'), t('Термины и определения проекта', 'Project terms and definitions'), button(t('Новый термин', 'New term'), 'term:new', 'plus', 'primary')) +
    '<div class="panel sheet">' + ((state.extra || []).map(term => '<div class="sheet-row"><div class="grow"><strong>' + escape(term.term) + '</strong><p>' +
      escape(term.definition) + '</p></div>' + iconButton('edit', 'term:' + term.id, t('Редактировать', 'Edit')) +
      iconButton('trash', 'extra-delete:glossary:' + term.id, t('Удалить', 'Delete')) + '</div>').join('') || empty(t('Терминов пока нет', 'No glossary terms yet'))) + '</div>'
}

function exportsPage() {
  return heading(t('История выгрузок', 'Export history'), t('Сохранённые версии BRD и SRS', 'Saved versions of BRD and SRS')) +
    '<div class="panel sheet">' + ((state.extra || []).slice().reverse().map(item => '<div class="sheet-row"><div><strong>' + escape(item.document_type) +
      ' · ' + escape(item.format.toUpperCase()) + ' · v' + escape(item.document_version) + '</strong><p class="muted">' +
      fmt(item.created_at) + ' · ' + escape(item.created_by) + '</p></div>' + button(t('Скачать', 'Download'), 'get-export:' + item.id, 'download') +
      '</div>').join('') || empty(t('Выгрузок пока нет', 'No exports yet'), '',
      button(t('Сформировать документ', 'Generate a document'), 'page:documents', 'file'))) + '</div>'
}

function settingsPage() {
  const project = state.projects.find(item => item.id === state.projectId)
  return heading(t('Настройки проекта', 'Project settings'), project.title, button(t('Изменить проект', 'Edit project'), 'edit-project', 'edit', 'primary')) +
    '<div class="panel sheet stack"><div><b>' + t('Заказчик', 'Customer') + '</b><p class="muted">' + escape(project.customer || '—') +
    '</p></div><div><b>' + t('Авторы', 'Authors') + '</b><p class="muted">' + escape(project.authors.join(', ') || '—') +
    '</p></div><div><b>' + t('Версия документа', 'Document version') + '</b><p class="muted">' + escape(project.document_version) +
    '</p></div><div class="flex">' + button(t('Импорт', 'Import'), 'import', 'upload') + button('JSON', 'backup:json', 'download') +
    button('CSV', 'backup:csv', 'download') + button(t('Удалить проект', 'Delete project'), 'delete-project', 'trash', 'danger') + '</div></div>'
}

function trashPage() {


  const rows = (state.extra || []).map(item => '<div class="sheet-row"><span>' + escape(item.code + ' · ' + item.title) + '</span>' +
    button(t('Восстановить', 'Restore'), 'restore-req:' + item.id, 'history') + '</div>')
  const projects = (state.deletedProjects || []).map(item => '<div class="sheet-row"><span>' + escape(item.title) + '</span>' +
    button(t('Восстановить проект', 'Restore project'), 'restore-project:' + item.id, 'history') + '</div>')
  return heading(t('Корзина', 'Trash'), t('Удалённые требования и проекты', 'Deleted requirements and projects')) +
    '<div class="panel sheet">' + ([...rows, ...projects].join('') || empty(t('Корзина пуста', 'Trash is empty'))) + '</div>'
}
let cleanupModal, activeMenu
const lineList = value => value.split(/\r?\n/).map(x => x.trim()).filter(Boolean)
const commaList = value => value.split(',').map(x => x.trim()).filter(Boolean)
const project = () => state.projects.find(p => p.id === state.projectId)
const reqOptions = (rows = state.rows) => rows.map(row => [row.id, row.code + ' · ' + row.title])
const saveLabel = () => t('Сохранить', 'Save')
const htmlForm = (controls, label) => '<form class="form">' + controls + footer(label) + '</form>'
const clearMenu = () => {
  activeMenu?.remove();
  activeMenu = null
}

function menu(anchor, items) {
  const rect = anchor.getBoundingClientRect()
  clearMenu()
  activeMenu = document.createElement('div')
  activeMenu.className = 'floating-menu'
  activeMenu.innerHTML = items.map(([label, action, symbol]) => button(label, action, symbol, 'ghost')).join('')
  document.body.append(activeMenu)
  activeMenu.style.left = Math.max(5, Math.min(rect.left, innerWidth - activeMenu.offsetWidth - 7)) + 'px'
  activeMenu.style.top = Math.max(5, Math.min(rect.bottom + 5, innerHeight - activeMenu.offsetHeight - 7)) + 'px'
  $('button', activeMenu)?.focus()
}

function closeModal() {
  cleanupModal?.()
  cleanupModal = null
  $('#modal-root').replaceChildren()
}

function modal(title, content, wide = false) {
  closeModal()
  $('#modal-root').innerHTML = '<div class="overlay"><section class="modal' + (wide ? ' wide' : '') +
    '" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div class="modal-head"><h2 id="dialog-title">' +
    escape(title) + '</h2>' + iconButton('x', 'close-modal', t('Закрыть', 'Close')) + '</div><div class="modal-body">' + content + '</div></section></div>'
  const overlay = $('.overlay')
  overlay.addEventListener('click', event => {
    if (event.target === overlay) closeModal()
  })
  const body = $('.modal-body', overlay);
  ($('input:not([type=checkbox]),textarea,select,button', body) || $('button', overlay))?.focus()
  return body
}

function modalForm(title, controls, submit, label = saveLabel(), wide = false) {
  const form = $('form', modal(title, htmlForm(controls, label), wide))
  form.addEventListener('submit', event => {
    event.preventDefault()
    const button = $('button[type=submit]', form)
    button.disabled = true
    run(async () => {
      try {
        await submit(formData(form), form)
      } finally {
        button.disabled = false
      }
    })
  })
  return form
}

function confirmAction(title, message, execute) {
  modalForm(title, '<p>' + escape(message) + '</p>', async () => {
    await execute();
    closeModal()
  }, t('Подтвердить', 'Confirm'))
}
async function loadPage(page = state.page) {
  state.page = page
  const extra = {
    sections: 'document-sections',
    glossary: 'glossary',
    exports: 'exports',
    trash: 'requirements?deleted=true'
  } [page]
  state.extra = extra && state.projectId ? await request(path(extra)) : []
  if (page === 'trash') state.deletedProjects = await request('/projects?deleted=true')
  if (state.page === page) render()
}
async function changeProject(id) {
  closeModal()
  Object.assign(state, {
    projectId: id,
    page: 'requirements',
    rows: [],
    tree: [],
    diagrams: [],
    current: null,
    details: {},
    filters: {},
    mode: 'tree',
    quick: null
  })
  state.collapsed.clear()
  state.selection.clear()
  if (id) localStorage.setItem('reqbase-project', id)
  else localStorage.removeItem('reqbase-project')
  await refresh()
}

function projectForm(item) {
  const controls = field(t('Название', 'Title'), input('title', item?.title, 'required')) +
    field(t('Код проекта', 'Project prefix'), input('prefix', item?.prefix || 'REQ', 'required')) +
    field(t('Описание', 'Description'), textarea('description', item?.description)) +
    field(t('Заказчик', 'Customer'), input('customer', item?.customer)) +
    field(t('Авторы через запятую', 'Authors, comma-separated'), input('authors', item?.authors.join(', '))) +
    '<div class="two-column">' + field(t('Версия документа', 'Document version'), input('document_version', item?.document_version || '1.0')) +
    field(t('Дата документа', 'Document date'), input('document_date', item?.document_date, 'type="date"')) + '</div>' +
    field(t('Язык документов', 'Document language'), select('locale', [
      ['ru', 'Русский'],
      ['en', 'English']
    ], item?.locale || state.locale))
  modalForm(item ? t('Редактировать проект', 'Edit project') : t('Новый проект', 'New project'), controls, async data => {
    data.authors = commaList(data.authors)
    if (item) data.expected_version = item.version
    const updated = await request(item ? '/projects/' + item.id : '/projects', item ? 'PATCH' : 'POST', data)
    state.projects = await request('/projects')
    if (!item) await changeProject(updated.id)
    else {
      closeModal();
      render()
    }
  })
}

function requirementForm(row, parent) {
  const contexts = parent ? reqOptions([parent]) : [
    ['', t('Корневой уровень', 'Root level')], ...reqOptions()
  ]
  const controls = field(t('Название', 'Title'), input('title', row?.title, 'required')) +
    '<div class="two-column">' + field(t('Тип', 'Type'), select('type', row?.parent_id ? types.slice(1) : types, row?.type || (parent ? 'FR' : 'BR'))) +
    (row ? field(t('Источник', 'Source'), input('source', row.source)) : field(t('Родитель', 'Parent'), select('parent_id', contexts, parent?.id || ''))) +
    '</div><div class="two-column">' + field(t('Статус', 'Status'), select('status', statuses, row?.status || 'Draft')) +
    field(t('Приоритет', 'Priority'), select('priority', priorities, row?.priority || 'Should')) + '</div>' +
    field(t('Описание в Markdown', 'Markdown description'), textarea('description', row?.description)) +
    field(t('Критерии приёмки, по одному на строку', 'Acceptance criteria, one per line'), textarea('acceptance_criteria', row?.acceptance_criteria.join('\n'))) +
    field(t('Теги через запятую', 'Tags, comma-separated'), input('tags', row?.tags.join(', '))) +
    (row ? '' : field(t('Источник', 'Source'), input('source')))
  const form = modalForm(row ? row.code + ' · ' + t('Редактировать', 'Edit') : t('Новое требование', 'New requirement'), controls, async data => {
    data.tags = commaList(data.tags)
    data.acceptance_criteria = lineList(data.acceptance_criteria)
    if (row) data.expected_version = row.version
    else data.parent_id = data.parent_id || null
    const result = await request(row ? '/requirements/' + row.id : path('requirements'), row ? 'PATCH' : 'POST', data)
    closeModal()
    state.current = result.items[0].id
    await refresh()
    toast(t('Требование сохранено', 'Requirement saved'))
  })
  const type = $('[name=type]', form)
  const parentInput = $('[name=parent_id]', form)
  const sync = () => {
    const isChild = Boolean(row ? row.parent_id : parentInput.value)
    for (const option of type.options) option.disabled = isChild === (option.value === 'BR')
    if (type.selectedOptions[0].disabled) type.value = isChild ? 'FR' : 'BR'
  }
  parentInput?.addEventListener('change', sync)
  sync()
}
async function updateRequirement(row, values) {
  await request('/requirements/' + row.id, 'PATCH', {
    ...values,
    expected_version: row.version
  })
  await refresh()
}

function inlineEdit(anchor, row, key) {
  const cell = anchor.closest('td')
  const original = cell.innerHTML
  cell.innerHTML = key === 'title' ? input('inline', row.title, 'aria-label="' + t('Название', 'Title') + '"') :
    select('inline', key === 'status' ? statuses : priorities, row[key], 'aria-label="' + (key === 'status' ? t('Статус', 'Status') : t('Приоритет', 'Priority')) + '"')
  const control = cell.firstElementChild
  let done = false
  const finish = save => {
    if (done) return
    done = true
    const value = control.value.trim()
    cell.innerHTML = original
    if (save && value && value !== row[key]) run(() => updateRequirement(row, {
      [key]: value
    }))
  }
  control.addEventListener('keydown', event => {
    if (!['Escape', 'Enter'].includes(event.key)) return
    event.stopPropagation()
    finish(event.key === 'Enter')
  })
  control.addEventListener('blur', () => finish(key === 'title'))
  control.addEventListener('change', () => finish(true))
  control.focus()
  if (key === 'title') control.select()
}

function bulkForm() {
  const ids = [...state.selection]
  modalForm(t('Массовое изменение', 'Bulk edit'),
    field(t('Статус', 'Status'), select('status', [
      ['', '—'], ...statuses
    ], '')) +
    field(t('Приоритет', 'Priority'), select('priority', [
      ['', '—'], ...priorities
    ], '')) +
    field(t('Новый набор тегов', 'Replacement tags'), input('tags')) +
    '<label class="check"><input type="checkbox" name="update_tags">' + t('Заменить теги', 'Replace tags') + '</label>', async data => {
      const values = removeEmpty({
        status: data.status,
        priority: data.priority
      })
      if (data.update_tags) values.tags = commaList(data.tags)
      if (!Object.keys(values).length) return
      const items = ids.map(rowById).filter(Boolean).map(row => ({
        id: row.id,
        expected_version: row.version,
        ...values
      }))
      await request('/requirements/bulk', 'PATCH', {
        items
      })
      state.selection.clear()
      closeModal()
      await refresh()
    })
}
async function moveRow(row, parent_id, position = null) {
  await request('/requirements/' + row.id + '/move', 'POST', {
    parent_id,
    position,
    expected_version: row.version
  })
  state.collapsed.delete(parent_id)
  await refresh()
}

function moveForm(row) {
  const descendants = new Set([row.id])
  for (let size = 0; size !== descendants.size;) {
    size = descendants.size
    for (const item of state.rows)
      if (descendants.has(item.parent_id)) descendants.add(item.id)
  }
  const choices = row.type === 'BR' ? [
    ['', t('Корневой уровень', 'Root level')]
  ] : reqOptions(state.rows.filter(item => !descendants.has(item.id)))
  modalForm(t('Переместить требование', 'Move requirement'), field(t('Родитель', 'Parent'), select('parent_id', choices, row.parent_id || '')) +
    field(t('Позиция среди соседей', 'Position among siblings'), input('position', '', 'type="number" min="1"')) +
    '<p class="form-note">' + t('Пустая позиция перемещает в конец списка.', 'Leave position blank to move to the end.') + '</p>', async data => {
      await moveRow(row, data.parent_id || null, data.position ? Number(data.position) - 1 : null)
      closeModal()
    })
}

function beginQuick(id, nest = false) {
  const row = rowById(id)
  state.quick = {
    anchor: row?.id || null,
    parent: nest ? row?.id || null : row?.parent_id || null,
    title: ''
  }
  render()
}
async function quickKey(event) {
  if (!['Escape', 'Tab', 'Enter'].includes(event.key)) return
  event.preventDefault()
  const quick = state.quick
  if (event.key === 'Escape') {
    state.quick = null;
    render();
    return
  }
  quick.title = event.target.value
  if (event.key === 'Tab') {
    quick.parent = event.shiftKey ? rowById(quick.parent)?.parent_id || null : quick.anchor
    render()
    return
  }
  if (!quick.title.trim()) return
  const anchor = rowById(quick.anchor)
  const position = anchor?.parent_id === quick.parent ? anchor.order + 1 : undefined
  event.target.disabled = true
  try {
    const result = await request(path('requirements'), 'POST', {
      title: quick.title,
      parent_id: quick.parent,
      type: quick.parent ? 'FR' : 'BR',
      position
    })
    state.current = result.items[0].id
    state.collapsed.delete(quick.parent)
    state.quick = null
    await refresh()
  } finally {
    event.target.disabled = false
  }
}
const sources = {
  mermaid: 'flowchart TD\n  A[Start] --> B[Finish]',
  plantuml: '@startuml\nAlice -> Bob: Hello\n@enduml'
}
const highlighting = StreamLanguage.define({
  token(stream) {
    if (stream.match(/(?:%%|').*/)) return 'comment'
    if (stream.match(/@[\w]+|\b(?:flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|actor|participant|class|skinparam|subgraph|end|alt|else|loop|activate|deactivate|start|stop|note|title)\b/i)) return 'keyword'
    if (stream.match(/(?:<-+|-+>|==>|--)/)) return 'operator'
    if (stream.match(/"[^"]*"|\[[^\]]*\]/)) return 'string'
    stream.next()
    return null
  }
})

function diagramForm(item, attached) {
  const controls = '<div class="two-column">' + field(t('Название', 'Title'), input('title', item?.title, 'required')) +
    '<div class="two-column">' + field(t('Язык', 'Language'), select('type', ['mermaid', 'plantuml'], item?.type || 'mermaid')) +
    field(t('Вид схемы', 'Diagram kind'), select('kind', kinds, item?.kind || 'flowchart')) + '</div></div>' +
    '<div class="two-column diagram-editor"><div><h3>' + t('Код схемы', 'Diagram code') + '</h3><div id="diagram-code"></div></div><div><h3>' +
    t('Предпросмотр', 'Preview') + '</h3><div id="diagram-preview" class="preview">…</div></div></div><div class="flex">' +
    button(t('Проверить через Kroki', 'Validate with Kroki'), 'validate-diagram', 'check') +
    (item ? button(t('Привязать к требованиям', 'Link requirements'), 'diagram-link:' + item.id, 'trace') + ['svg', 'png'].map(format => button(format.toUpperCase(), 'download-diagram:' + item.id + ':' + format, 'download')).join('') : '') + '</div>'
  let editor
  const form = modalForm(item?.title || t('Новая схема', 'New diagram'), controls, async data => {
    data.source = editor.state.doc.toString()
    if (item) data.expected_version = item.version
    if (attached) data.requirement_ids = [attached]
    await request(path(item ? 'diagrams/' + item.id : 'diagrams'), item ? 'PATCH' : 'POST', data)
    closeModal()
    await refresh()
  }, undefined, true)
  const type = $('[name=type]', form)
  const preview = $('#diagram-preview', form)
  let timer, url, sequence = 0
  async function draw() {
    const seq = ++sequence
    try {
      const source = editor.state.doc.toString()
      const image = type.value === 'mermaid' ? await drawMermaid(source) :
        await request('/diagrams/render', 'POST', {
          type: type.value,
          source
        }, 'blob')
      if (seq !== sequence) return
      if (url) URL.revokeObjectURL(url)
      url = URL.createObjectURL(image)
      preview.innerHTML = '<img alt="' + t('Предпросмотр схемы', 'Diagram preview') + '" src="' + url + '">'
    } catch (error) {
      if (seq === sequence) preview.innerHTML = '<div class="preview-error">' + escape(error.message) + '</div>'
    }
  }

  function delay() {
    clearTimeout(timer);
    timer = setTimeout(draw, 240)
  }
  editor = new EditorView({
    doc: item?.source || sources[type.value],
    parent: $('#diagram-code', form),
    extensions: [basicSetup, highlighting, EditorView.updateListener.of(event => {
      if (event.docChanged) delay()
    })]
  })
  let previous = type.value
  type.addEventListener('change', () => {
    const value = editor.state.doc.toString()
    if (!value.trim() || value === sources[previous]) editor.dispatch({
      changes: {
        from: 0,
        to: value.length,
        insert: sources[type.value]
      }
    })
    previous = type.value
    delay()
  })
  form.validateDiagram = async () => {
    const result = await request('/diagrams/validate', 'POST', {
      type: type.value,
      source: editor.state.doc.toString()
    })
    if (result.valid) toast(t('Синтаксис корректен', 'Diagram syntax is valid'))
    else toast((result.line ? t('Строка', 'Line') + ' ' + result.line + ' · ' : '') + result.error, true)
  }
  cleanupModal = () => {
    sequence++;
    clearTimeout(timer);
    editor.destroy();
    if (url) URL.revokeObjectURL(url)
  }
  draw()
}
async function fullDiagram(item) {
  const body = modal(item.title, '<div class="flex">' + button(t('Редактировать', 'Edit'), 'diagram:' + item.id, 'edit') + ['svg', 'png'].map(f => button(f.toUpperCase(), 'download-diagram:' + item.id + ':' + f, 'download')).join('') + '</div><div class="preview" id="full-preview"></div>', true)
  body.closest('.modal').classList.add('diagram-full')
  try {
    const url = await thumbUrl(item)
    $('#full-preview', body).innerHTML = '<img alt="' + escape(item.title) + '" src="' + url + '">'
  } catch (error) {
    $('#full-preview', body).textContent = error.message
  }
}
async function linkDiagram(item) {
  const links = await request(path('requirement-diagrams'))
  const existing = new Set(links.filter(link => link.diagram_id === item.id).map(link => link.requirement_id))
  const choices = reqOptions(state.rows.filter(row => !existing.has(row.id)))
  const title = t('Привязать к требованиям', 'Link to requirements')
  if (!choices.length) {
    modal(title, empty(t('Нет доступных требований', 'No available requirements')));
    return
  }
  modalForm(title, field(t('Требования', 'Requirements'), select('requirement_ids', choices, null, 'multiple required')), async (_, form) => {
    const requirement_ids = new FormData(form).getAll('requirement_ids')
    await request(path('diagrams/' + item.id), 'PATCH', {
      requirement_ids,
      expected_version: item.version
    })
    closeModal()
    await refresh()
  }, t('Привязать', 'Link'))
}

function createAssociation(collection, title, label, choices, key, fixed, extra = '') {
  if (!choices.length) {
    modal(title, empty(t('Нет доступных объектов', 'No available records')));
    return
  }
  modalForm(title, field(label, select(key, choices, null, 'required')) + extra, async data => {
    await request(path(collection), 'POST', {
      ...data,
      ...fixed
    })
    closeModal()
    await refresh()
  }, t('Привязать', 'Link'))
}
// Application interactions

function documentForm(document_type) {
  const body = modal(t('Сформировать', 'Generate') + ' ' + document_type, '<form class="form">' +
    '<div class="flex"><label class="check"><input type="checkbox" name="approved_only">' + t('Только Approved', 'Approved only') +
    '</label><label class="check"><input type="checkbox" name="exclude_rejected" checked>' + t('Исключить Rejected', 'Exclude Rejected') + '</label></div>' +
    field(t('Выбранные ветки (пусто — весь проект)', 'Selected branches (empty means entire project)'),
      select('branch_ids', reqOptions(), null, 'multiple size="3"')) +
    '<div class="flex"><button class="primary" type="submit">' + icon('file') + t('Предпросмотр', 'Preview') +
    '</button>' + button('PDF', 'export-current:pdf', 'download') + button('Markdown', 'export-current:md', 'download') +
    '</div><div id="doc-preview" class="document-preview markdown hidden"></div></form>', true)
  const form = $('form', body)
  const data = () => {
    const fields = new FormData(form)
    return {
      document_type,
      filters: {
        approved_only: fields.has('approved_only'),
        exclude_rejected: fields.has('exclude_rejected'),
        branch_ids: fields.getAll('branch_ids')
      }
    }
  }
  form.exportDocument = async format => {
    const result = await request(path('exports'), 'POST', {
      ...data(),
      format
    })
    await download(result.download_url, result.filename)
    toast(t('Выгрузка сохранена', 'Export saved'))
  }
  form.addEventListener('submit', event => {
    event.preventDefault()
    const preview = $('#doc-preview', form)
    preview.classList.remove('hidden')
    preview.textContent = t('Сборка документа…', 'Assembling document…')
    run(async () => {
      try {
        const result = await request(path('exports/preview'), 'POST', data())
        preview.innerHTML = markdown(result.markdown)
      } catch (error) {
        preview.textContent = error.message;
        throw error
      }
    })
  })
}

function importForm(restore = false) {
  modalForm(t('Импорт', 'Import'), '<label class="file-drop">' + t('Выберите файл', 'Choose a file') +
    '<input name="file" type="file" accept="' + (restore ? '.json' : '.json,.csv') + '" required></label>' +
    '<p class="form-note">' + (restore ? t('Резервная копия восстанавливается в отдельный проект.', 'Restore a backup as a separate project.') :
      t('Импорт добавляет требования в текущий проект.', 'Import appends requirements to the current project.')) + '</p>', async ({
      file
    }) => {
      const content = await file.text()
      if (restore) {
        const result = await request('/projects/import', 'POST', {
          content
        })
        state.projects = await request('/projects')
        await changeProject(result.id)
      } else {
        await request(path('import'), 'POST', {
          content,
          format: file.name.toLowerCase().endsWith('.csv') ? 'csv' : 'json'
        })
        closeModal()
        await refresh()
      }
      toast(t('Импорт завершён', 'Import complete'))
    }, t('Импортировать', 'Import'))
}

function editExtra(collection, row, title, controls, extra = {}) {
  modalForm(title, controls, async data => {
    const id = row?.id
    if (id) data.expected_version = row.version
    await request(path(collection + (id ? '/' + id : '')), id ? 'PATCH' : 'POST', {
      ...data,
      ...extra
    })
    closeModal()
    if (state.page === 'requirements') await refresh()
    else await loadPage()
  })
}

function itemDelete(collection, item) {
  confirmAction(t('Удалить запись', 'Delete record'), t('Запись будет перемещена в корзину.', 'This record will be moved to the trash.'), async () => {
    await request(path(collection + '/' + item.id), 'DELETE', {
      expected_version: item.version
    })
    if (['requirements', 'diagrams'].includes(state.page)) await refresh()
    else await loadPage()
  })
}

function saveView() {
  modalForm(t('Сохранить представление', 'Save view'), field(t('Название', 'Title'), input('title', '', 'required')), async data => {
    await request(path('views'), 'POST', {
      ...data,
      mode: state.mode,
      filters: removeEmpty(state.filters)
    })
    closeModal()
    await refresh()
  })
}


async function action(name, anchor) {
  const [key, id, part] = name.split(':')
  const row = rowById(id)
  const diagram = state.diagrams.find(item => item.id === id)
  const handlers = {
    'close-modal': closeModal,
    'mobile-nav': () => menu(anchor, [...Object.entries(pageLabels()).map(([id, [icon, label]]) => [label, 'page:' + id, icon]), [t('Сменить проект', 'Switch project'), 'projects', 'gear'],
      [t('Язык', 'Language'), 'locale', 'gear']
    ]),
    'locale': () => {
      state.locale = state.locale === 'ru' ? 'en' : 'ru';
      localStorage.setItem('reqbase-locale', state.locale);
      render()
    },
    'page': () => loadPage(id),
    'refresh': async () => {
      state.projects = await request('/projects');
      await refresh();
      await loadPage()
    },
    'projects': () => menu(anchor, [...state.projects.map(p => [p.title, 'pick-project:' + p.id, 'tree']),
      [t('Новый проект', 'New project'), 'new-project', 'plus'],
      [t('Из копии JSON', 'Restore JSON backup'), 'restore-backup', 'upload']
    ]),
    'pick-project': () => changeProject(id),
    'new-project': () => projectForm(),
    'edit-project': () => projectForm(project()),
    'delete-project': () => confirmAction(t('Удалить проект', 'Delete project'), project().title, async () => {
      const current = project()
      await request('/projects/' + current.id, 'DELETE', {
        expected_version: current.version
      })
      state.projects = await request('/projects')
      await changeProject(state.projects[0]?.id || null)
    }),
    'restore-project': async () => {
      const current = state.deletedProjects.find(p => p.id === id)
      await request('/projects/' + id + '/restore', 'POST', {
        expected_version: current.version
      })
      state.projects = await request('/projects')
      await changeProject(id)
    },
    'new-req': () => requirementForm(),
    'child': () => requirementForm(null, row),
    'edit-req': () => requirementForm(row),
    'row': () => selectRow(id),
    'jump': async () => {
      state.page = 'requirements';
      await selectRow(id)
    },
    'close-row': () => {
      state.current = null;
      render()
    },
    'tab': () => {
      state.tab = id;
      render()
    },
    'mode': () => {
      state.mode = id;
      state.quick = null;
      render()
    },
    'fold': () => {
      if (!state.collapsed.delete(id)) state.collapsed.add(id);
      render()
    },
    'filters': () => {
      state.showFilters = !state.showFilters;
      render()
    },
    'reset-filters': () => {
      state.filters = {};
      return refresh()
    },
    'grid-menu': () => menu(anchor, [
      [t('Развернуть всё', 'Expand all'), 'expand', 'down'],
      [t('Свернуть всё', 'Collapse all'), 'collapse', 'right'],
      [t('Быстро добавить', 'Quick add'), 'quick', 'plus']
    ]),
    'expand': () => {
      state.collapsed.clear();
      render()
    },
    'collapse': () => {
      state.collapsed = new Set(state.rows.map(row => row.parent_id).filter(Boolean));
      render()
    },
    'quick': () => beginQuick(state.current),
    'clear-selection': () => {
      state.selection.clear();
      render()
    },
    'bulk': bulkForm,
    'inline': () => inlineEdit(anchor, rowById(part), id),
    'row-menu': () => menu(anchor, [
      [t('Редактировать', 'Edit'), 'edit-req:' + id, 'edit'],
      [t('Добавить дочернее', 'Add child'), 'child:' + id, 'plus'],
      [t('Переместить', 'Move'), 'move:' + id, 'trace'],
      [t('Удалить', 'Delete'), 'delete-req:' + id, 'trash']
    ]),
    'move': () => moveForm(row),
    'delete-req': () => confirmAction(t('Удалить требование', 'Delete requirement'),
      t('Будет удалено требование вместе с его дочерними требованиями.', 'The requirement and its descendants will be deleted.'), async () => {
        await request('/requirements/' + id, 'DELETE', {
          expected_version: row.version
        })
        await refresh()
      }),
    'restore-req': async () => {
      const deleted = state.extra.find(item => item.id === id)
      await request('/requirements/' + id + '/restore', 'POST', {
        expected_version: deleted.version
      })
      await refresh()
      await loadPage()
    },
    'rollback': () => confirmAction(t('Откатить изменение', 'Roll back change'),
      t('Состояние требования восстановится из выбранной записи истории.', 'Restore the requirement from this history entry.'), async () => {
        const current = rowById(state.current)
        await request('/requirements/' + current.id + '/rollback', 'POST', {
          expected_version: current.version,
          history_id: id
        })
        await refresh()
      }),
    'views': () => menu(anchor, [
      [t('Сохранить текущий вид', 'Save current view'), 'save-view', 'plus'],
      ...state.views.flatMap(v => [
        [v.title, 'apply-view:' + v.id, 'book'],
        [t('Удалить', 'Delete') + ' · ' + v.title, 'delete-view:' + v.id, 'trash']
      ])
    ]),
    'save-view': saveView,
    'apply-view': () => {
      const view = state.views.find(v => v.id === id)
      state.mode = view.mode;
      state.filters = {
        ...view.filters
      };
      state.showFilters = Boolean(Object.keys(view.filters).length)
      return refresh()
    },
    'delete-view': () => itemDelete('views', state.views.find(v => v.id === id)),
    'diagram': () => diagramForm(diagram, part === 'attached' ? state.current : null),
    'diagram-menu': () => menu(anchor, [
      [t('Привязать к требованиям', 'Link requirements'), 'diagram-link:' + id, 'trace'],
      ['SVG', 'download-diagram:' + id + ':svg', 'download'],
      ['PNG', 'download-diagram:' + id + ':png', 'download'],
      [t('Удалить', 'Delete'), 'delete-diagram:' + id, 'trash']
    ]),
    'delete-diagram': () => itemDelete('diagrams', diagram),
    'full': () => fullDiagram(diagram),
    'validate-diagram': () => anchor.closest('form').validateDiagram(),
    'download-diagram': () => download('/diagrams/' + id + '/render?format=' + part + '&download=true', diagram.title + '.' + part),
    'diagram-link': () => linkDiagram(diagram),
    'attach': () => {
      const linked = new Set((state.details.attachments || []).map(item => item.diagram_id))
      return createAssociation('requirement-diagrams', t('Прикрепить схему', 'Attach diagram'), t('Схема', 'Diagram'),
        state.diagrams.filter(item => !linked.has(item.id)).map(item => [item.id, item.title]), 'diagram_id', {
          requirement_id: state.current
        })
    },
    'link': () => createAssociation('links', t('Добавить связь', 'Add link'), t('Требование', 'Requirement'),
      reqOptions(state.rows.filter(row => row.id !== state.current)), 'target_id', {
        source_id: state.current
      },
      field(t('Тип связи', 'Relationship'), select('type', linkTypes, 'depends_on'))),
    'item-delete': () => itemDelete(id, (state.details[{
      comments: 'comments',
      links: 'links',
      'requirement-diagrams': 'attachments'
    } [id]] || []).find(item => item.id === part)),
    'extra-delete': () => itemDelete(id, state.extra.find(item => item.id === part)),
    'comment-edit': () => {
      const item = state.details.comments.find(row => row.id === id)
      return editExtra('comments', item, t('Править комментарий', 'Edit comment'), field(t('Комментарий', 'Comment'), textarea('body', item.body)))
    },
    'section': () => {
      const item = state.extra.find(row => row.key === id)
      return editExtra('document-sections', item, t(...sectionLabels[id]), field('Markdown', textarea('body', item?.body)), {
        key: id
      })
    },
    'term': () => {
      const item = state.extra.find(row => row.id === id)
      return editExtra('glossary', item, t('Термин', 'Term'), field(t('Термин', 'Term'), input('term', item?.term, 'required')) +
        field(t('Определение', 'Definition'), textarea('definition', item?.definition)))
    },
    'document': () => documentForm(id),
    'export-current': async () => {
      anchor.disabled = true
      try {
        await anchor.closest('form').exportDocument(id)
      } finally {
        anchor.disabled = false
      }
    },
    'get-export': () => {
      const item = state.extra.find(row => row.id === id)
      return download(item.download_url, item.filename)
    },
    'backup': () => download(path('backup') + '?format=' + id, project().prefix + '.' + id),
    'import': () => importForm(),
    'restore-backup': () => importForm(true)
  }
  return handlers[key]?.()
}
let searchTimer
document.addEventListener('input', event => {
  const target = event.target
  if (target.id !== 'global-search') return
  state.filters.q = target.value
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => run(async () => {
    state.page = 'requirements';
    await refresh()
  }), 210)
})
document.addEventListener('change', event => {
  const target = event.target
  if (target.matches('[data-filter]')) {
    state.filters[target.name] = target.name === 'has_diagrams' && target.value ? target.value === 'true' : target.value
    run(refresh)
  } else if (target.matches('[data-pick]')) {
    if (target.checked) state.selection.add(target.dataset.pick)
    else state.selection.delete(target.dataset.pick)
    render()
  } else if (target.id === 'select-all') {
    for (const tr of document.querySelectorAll('tr[data-row]')) {
      if (target.checked) state.selection.add(tr.dataset.row)
      else state.selection.delete(tr.dataset.row)
    }
    render()
  }
})
document.addEventListener('submit', event => {
  if (event.target.id !== 'comment-form') return
  event.preventDefault()
  const form = event.target
  const submit = $('button', form)
  submit.disabled = true
  run(async () => {
    try {
      await request(path('comments'), 'POST', {
        ...formData(form),
        requirement_id: state.current
      })
      await refresh()
    } finally {
      submit.disabled = false
    }
  })
})
document.addEventListener('click', event => {
  const control = event.target.closest('[data-action]')
  if (!control || !['projects', 'mobile-nav'].includes(control.dataset.action)) clearMenu()
  if (control) {
    if (control.classList.contains('title-control') && control.closest('[data-row]').dataset.row === state.current) return
    run(() => action(control.dataset.action, control))
  } else if (!event.target.closest('input,select,textarea,button')) {
    const row = event.target.closest('[data-row]')
    if (row && row.dataset.row !== state.current) run(() => selectRow(row.dataset.row))
  }
})
document.addEventListener('dblclick', event => {
  const control = event.target.closest('.title-control')
  if (control) inlineEdit(control, rowById(control.closest('[data-row]').dataset.row), 'title')
})
document.addEventListener('keydown', event => {
  const target = event.target
  if (target.id === 'quick-title') {
    run(() => quickKey(event));
    return
  }
  if (event.key === 'Escape') {
    if ($('#modal-root').firstElementChild) closeModal()
    else if (activeMenu) clearMenu()
    else if (state.current) {
      state.current = null;
      render()
    }
    return
  }
  if (target.closest('input,textarea,select,[contenteditable],.overlay,button')) return
  if (event.key === '/') {
    event.preventDefault();
    $('#global-search')?.focus();
    return
  }
  const row = target.closest('[data-row]')
  if (event.key === 'F2' && row && $('.title-control', row)) {
    event.preventDefault()
    inlineEdit($('.title-control', row), rowById(row.dataset.row), 'title')
  } else if (event.key === 'Enter' && state.projectId && state.page === 'requirements') {
    event.preventDefault()
    if (state.mode === 'kanban' && row) run(() => selectRow(row.dataset.row))
    else beginQuick(row?.dataset.row || state.current)
  }
})

function dropTarget(event) {
  return event.target.closest(state.mode === 'kanban' ? '.lane' : 'tr[data-row]')
}
document.addEventListener('dragstart', event => {
  const row = event.target.closest('[data-row]')
  if (!row) return
  state.drag = row.dataset.row
  event.dataTransfer.setData('text/plain', state.drag)
  event.dataTransfer.effectAllowed = 'move'
})
document.addEventListener('dragover', event => {
  if (!state.drag) return
  const target = dropTarget(event)
  if (!target || target.dataset.row === state.drag) return
  event.preventDefault()
  for (const previous of document.querySelectorAll('.drop-target'))
    if (previous !== target) previous.classList.remove('drop-target')
  target.classList.add('drop-target')
})

function endDrag() {
  state.drag = null
  for (const target of document.querySelectorAll('.drop-target')) target.classList.remove('drop-target')
}
document.addEventListener('dragend', endDrag)
document.addEventListener('drop', event => {
  const target = dropTarget(event)
  const moving = rowById(state.drag)
  endDrag()
  if (!moving || !target || target.dataset.row === moving.id) return
  event.preventDefault()
  if (target.dataset.lane) {
    run(() => updateRequirement(moving, {
      status: target.dataset.lane
    }));
    return
  }
  const destination = rowById(target.dataset.row)
  const rect = target.getBoundingClientRect()
  const ratio = (event.clientY - rect.top) / rect.height
  if (ratio > .25 && ratio < .75 && moving.type !== 'BR') {
    run(() => moveRow(moving, destination.id))
    return
  }
  const parent = destination.parent_id
  let position = destination.order + (ratio >= .5 ? 1 : 0)
  if (moving.parent_id === parent && moving.order < position) position--
  run(() => moveRow(moving, parent, position))
})

render()
boot().catch(error => {
  state.loading = false
  render()
  toast(error.message, true)
})
