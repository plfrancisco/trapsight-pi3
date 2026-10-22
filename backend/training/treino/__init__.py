"""Treino da U-Net de segmentação em três classes.

A especificação normativa está em `.context/plan/model/treino_spec.md`. Cada
módulo tem uma responsabilidade: configuração, dados, aumentos, perda, modelo,
métricas, seleção do melhor ponto, loop e linha de comando.
"""

import os

# Cada processo de leitura de dados importa o NumPy; sem este limite, o OpenBLAS
# abre uma thread por núcleo em cada um e falha ao reservar memória em máquinas
# com pouca RAM livre. Precisa ser definido antes de o NumPy ser importado.
for _variavel in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variavel, "1")
