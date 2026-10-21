import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CampoFormulario from './CampoFormulario'

describe('CampoFormulario', () => {
  it('associa o rótulo, a descrição e o erro ao campo', () => {
    render(
      <CampoFormulario
        descricao="Use um identificador curto e único."
        erro="Já existe uma armadilha com este identificador."
        id="identificador"
        nome="identificador"
        obrigatorio
        rotulo="Identificador"
      />,
    )

    const campo = screen.getByRole('textbox', { name: 'Identificador' })
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(campo).toHaveAttribute('aria-describedby', 'identificador-ajuda identificador-erro')
    expect(screen.getByText('Use um identificador curto e único.')).toBeVisible()
    expect(
      screen.getByText('Já existe uma armadilha com este identificador.'),
    ).toBeVisible()
  })

  it('apresenta a data como somente leitura quando o cadastro está em edição', () => {
    render(
      <CampoFormulario
        id="data-instalacao"
        nome="data_instalacao"
        rotulo="Data de instalação"
        somenteLeitura
        tipo="date"
        valorPadrao="2026-10-14"
      />,
    )

    expect(screen.getByLabelText('Data de instalação')).toHaveValue('2026-10-14')
    expect(screen.getByLabelText('Data de instalação')).toHaveAttribute('readonly')
  })
})
