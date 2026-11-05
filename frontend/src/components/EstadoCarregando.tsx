/** Informa que o conteúdo solicitado ainda está sendo carregado.
 * O indicador só aparece depois de um instante, para não piscar em respostas rápidas.
 */
export default function EstadoCarregando() {
  return (
    <div aria-live="polite" className="estado-carregando" role="status">
      <span aria-hidden="true" className="estado-carregando__giro" />
      Carregando…
    </div>
  )
}
