import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const diretorioFrontend = resolve(fileURLToPath(new URL('..', import.meta.url)))
const caminhoWorker = resolve(diretorioFrontend, 'dist', 'sw.js')

function falhar(mensagem) {
  console.error(`Verificação do service worker falhou: ${mensagem}`)
  process.exitCode = 1
}

let codigoWorker
try {
  codigoWorker = readFileSync(caminhoWorker, 'utf8')
} catch {
  falhar('dist/sw.js não existe; execute npm run build primeiro.')
  process.exit()
}
const codigoWorkerEmUmaLinha = codigoWorker.replace(/\s+/g, ' ')

const manifestoInjetado = codigoWorker.match(
  /(?:const|let|var)\s+manifestoInjetado\s*=\s*(\[[\s\S]*?\]);/,
)
if (!manifestoInjetado) {
  falhar('não foi possível localizar a lista de precache injetada.')
  process.exit()
}

let entradasInjetadas
try {
  entradasInjetadas = JSON.parse(manifestoInjetado[1])
} catch {
  falhar('a lista de precache injetada não é JSON válido.')
  process.exit()
}

if (!/manifestoDoCasco\s*=\s*manifestoInjetado\.filter\(arquivoPertenceAoCasco\)/.test(codigoWorker)) {
  falhar('a lista injetada não é filtrada antes de chegar ao precache.')
}
if (!/precacheAndRoute\(manifestoDoCasco\)/.test(codigoWorker)) {
  falhar('o precache não usa exclusivamente a lista filtrada do casco.')
}
if (!/arquivoPertenceAoCasco\s*=\s*\(entrada\)\s*=>/.test(codigoWorker)) {
  falhar('não foi encontrada a regra de filtragem do casco.')
}
if (!/url\s*===\s*["']index\.html["']/.test(codigoWorker) ||
    !/url\.startsWith\(["']assets\/["']\)/.test(codigoWorker) ||
    !/\^icons\\\/\[\^\/\]\+\\\.png\$/.test(codigoWorker)) {
  falhar('a regra de filtragem do casco não corresponde a index.html, assets/** e icons/*.png.')
}

const entradas = entradasInjetadas.filter((entrada) => {
  if (typeof entrada?.url !== 'string') return false
  const url = new URL(entrada.url, 'https://trapsight.invalid')
  const caminho = decodeURIComponent(url.pathname)
  return (
    url.origin === 'https://trapsight.invalid' &&
    (caminho === '/index.html' ||
      caminho.startsWith('/assets/') ||
      /^\/icons\/[^/]+\.png$/i.test(caminho))
  )
})

for (const entrada of entradas) {
  if (typeof entrada?.url !== 'string') {
    falhar('uma entrada do precache não tem URL textual.')
    continue
  }

  const url = new URL(entrada.url, 'https://trapsight.invalid')
  const caminho = decodeURIComponent(url.pathname)
  const permitido =
    url.origin === 'https://trapsight.invalid' &&
    (caminho === '/index.html' ||
      caminho.startsWith('/assets/') ||
      /^\/icons\/[^/]+\.png$/i.test(caminho))

  if (!permitido) falhar(`arquivo fora do casco no precache: ${entrada.url}`)
}

const requisicoesSempreNaRede =
  /registerRoute\(\(\{ request, url \}\) => request\.method !== ["']GET["'] \|\| url\.origin !== self\.location\.origin \|\| caminhoApi\.test\(url\.pathname\), new NetworkOnly\(\)\)/
if (!requisicoesSempreNaRede.test(codigoWorkerEmUmaLinha)) {
  falhar('API, métodos diferentes de GET e outras origens não compartilham uma rota NetworkOnly.')
}
if (!/denylist:\s*\[\s*\/\^\\\/api\\\/\//.test(codigoWorker)) {
  falhar('a rota de navegação não exclui /api/ do fallback do casco.')
}
if (!/return await fetch\(request\);[\s\S]*?return await matchPrecache\(["']\/index\.html["']\)/.test(codigoWorker)) {
  falhar('a navegação não tenta a rede antes de usar index.html em cache.')
}
if (/new (?:CacheFirst|NetworkFirst|StaleWhileRevalidate)\(/.test(codigoWorker)) {
  falhar('foi encontrada uma estratégia de cache em tempo de execução fora do precache estático.')
}

if (process.exitCode !== 1) {
  console.log(`Service worker seguro: ${entradas.length} arquivos estáticos no precache.`)
}
