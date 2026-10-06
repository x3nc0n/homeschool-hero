const XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const FILE_MIME_TYPES: Record<string, string[]> = {
  '.txt': ['text/plain'],
  '.md': ['text/markdown', 'text/plain'],
  '.json': ['application/json', 'text/json', 'text/plain'],
  '.csv': ['text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel'],
  '.tsv': ['text/tab-separated-values', 'text/tsv', 'text/plain'],
  '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  '.pdf': ['application/pdf'],
  '.xlsx': [XLSX_MIME_TYPE, 'application/zip'],
}
const ACCEPTED_EXTENSIONS = Object.keys(FILE_MIME_TYPES)
const ACCEPTED_MIME_TYPES = [...new Set(Object.values(FILE_MIME_TYPES).flat())]
export const ASSIGNMENT_IMPORT_FILE_TYPES = `${ACCEPTED_EXTENSIONS.join(',')},${ACCEPTED_MIME_TYPES.join(',')}`
export const MAX_ASSIGNMENT_IMPORT_FILE_BYTES = 10 * 1024 * 1024

export function validateAssignmentImportFile(file: Pick<File, 'name' | 'type' | 'size'>): string | null {
  const name = file.name.toLowerCase()
  const mime = file.type.toLowerCase().split(';', 1)[0].trim()
  const extension = ACCEPTED_EXTENSIONS.find((extension) => name.endsWith(extension))
  const hasAllowedMime = extension && ['', 'application/octet-stream', ...FILE_MIME_TYPES[extension]].includes(mime)
  if (!extension || !hasAllowedMime) {
    return 'Please choose a .txt, .md, .json, .csv, .tsv, .docx, .pdf, or unencrypted .xlsx file with a matching file type. Legacy .xls files are not supported.'
  }
  if (file.size > MAX_ASSIGNMENT_IMPORT_FILE_BYTES) {
    return 'That file is larger than 10 MB. Please split the plan or choose a smaller file.'
  }
  return null
}
