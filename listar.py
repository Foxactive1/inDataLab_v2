import os
from datetime import datetime


def listar_pasta_corrente_txt():
    """
    Gera arquivo TXT com a estrutura
    da pasta corrente e subpastas.
    """

    pasta_raiz = os.getcwd()

    nome_projeto = os.path.basename(
        pasta_raiz
    )

    arquivo_saida = os.path.join(
        pasta_raiz,
        'estrutura_projeto.txt'
    )

    ignorar = {
        '__pycache__',
        '.git',
        '.venv',
        'venv',
        'node_modules',
        '.idea',
        '.vscode'
    }

    linhas = []

    linhas.append(
        f"Projeto: {nome_projeto}"
    )

    linhas.append(
        f"Gerado em: {datetime.now()}"
    )

    linhas.append("=" * 60)

    for raiz, diretorios, arquivos in os.walk(
        pasta_raiz
    ):

        # Ignorar diretórios
        diretorios[:] = [
            d for d in diretorios
            if d not in ignorar
        ]

        nivel = raiz.replace(
            pasta_raiz,
            ''
        ).count(os.sep)

        indentacao = '│   ' * nivel

        nome_dir = os.path.basename(raiz)

        if nivel == 0:
            linhas.append(
                f"📁 {nome_dir}/"
            )
        else:
            linhas.append(
                f"{indentacao}├── 📁 {nome_dir}/"
            )

        sub_indentacao = (
            '│   ' * (nivel + 1)
        )

        for arquivo in arquivos:

            if arquivo in ignorar:
                continue

            caminho_arquivo = os.path.join(
                raiz,
                arquivo
            )

            try:

                tamanho = os.path.getsize(
                    caminho_arquivo
                )

                tamanho_kb = round(
                    tamanho / 1024,
                    2
                )

                linhas.append(
                    f"{sub_indentacao}"
                    f"├── 📄 {arquivo} "
                    f"({tamanho_kb} KB)"
                )

            except Exception:

                linhas.append(
                    f"{sub_indentacao}"
                    f"├── 📄 {arquivo}"
                )

    with open(
        arquivo_saida,
        'w',
        encoding='utf-8'
    ) as f:

        f.write('\n'.join(linhas))

    print(
        f"\n✅ Estrutura gerada com sucesso!"
    )

    print(
        f"📄 Arquivo: {arquivo_saida}"
    )


if __name__ == '__main__':

    listar_pasta_corrente_txt()