# CÓDIGO ANTIGO - COM BUG
if fc_max_input:
    tempo_por_zona = analisar_zonas_fc(df, fc_max_input)
    total_tempo = tempo_por_zona.sum()

    # Criando um DataFrame para exibir a tabela formatada
    tabela_zonas = pd.DataFrame(tempo_por_zona).rename(columns={0: 'Tempo (s)'})
    tabela_zonas['Tempo'] = tabela_zonas['Tempo (s)'].apply(formatar_tempo_min_seg)
    tabela_zonas['Percentual'] = (tabela_zonas['Tempo (s)'] / total_tempo * 100).map('{:.1f}%'.format)
    st.table(tabela_zonas[['Tempo', 'Percentual']])