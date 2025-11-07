from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
    FilterExpression, Filter, FilterExpressionList
)
from pandas.core.internals.blocks import compare_or_regex_search


def session_lucegas_filter() -> FilterExpression:
    """
    Filtro per pagine luce/gas ED esclusione pagine che iniziano con 'pp.'
    
    Logica: (pageLocation inizia con '/offerta/casa/gas-e-luce') AND NOT (fullPageUrl inizia con 'pp.')
    """
    return FilterExpression(
        and_group=FilterExpressionList(
            expressions=[
                # Primo elemento dell'AND: pagine luce/gas
                FilterExpression(
                    filter=Filter(
                        field_name='pageLocation',
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.CONTAINS,
                            value='/offerta/casa/gas-e-luce'
                        )
                    )
                ),
                # Secondo elemento dell'AND: esclusione pagine pp.
                FilterExpression(
                    not_expression=FilterExpression(
                        filter=Filter(
                            field_name='fullPageUrl',
                            string_filter=Filter.StringFilter(
                                match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                                value='pp.'
                            )
                        )
                    )
                )
            ]
        )
    )

def session_commodity_filter() -> FilterExpression:
    """Equivalente al filtro JavaScript filter_PP_PL"""
    return FilterExpression(
        and_group=FilterExpressionList(  # ← CAMBIATO
            expressions=[
                FilterExpression(
                    or_group=FilterExpressionList(
                        expressions=[
                            FilterExpression(
                                filter=Filter(
                                    field_name='pagePath',  # ← CAMBIATO
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                                        value='offerta/casa'  # ← CAMBIATO
                                    )
                                )
                            ),
                            FilterExpression(
                                filter=Filter(
                                    field_name='pagePath',  # ← CAMBIATO
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                                        value='offerte/casa'
                                    )
                                )
                            ),
                            FilterExpression(
                                filter=Filter(
                                    field_name='pagePath',  # ← CAMBIATO
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                                        value='offerta/business'
                                    )
                                )
                            ),
                            FilterExpression(
                                filter=Filter(
                                    field_name='pagePath',  # ← CAMBIATO
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                                        value='offerte/business'
                                    )
                                )
                            )
                        ]
                    )
                )
                # ← RIMOSSA la parte NOT expression
            ]
        )
    )

def funnel_weborder_step1_filter() -> FilterExpression:
    """
    Filtro per primo step funnel: pagina contiene weborder/1_i_tuoi_dati/1/
    e non inizia con pp.
    """
    return FilterExpression(
        and_group=FilterExpressionList(
            expressions=[
                FilterExpression(
                    filter=Filter(
                        field_name='customEvent:macro_step',
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value='anagrafica'
                        )
                    )
                ),
                FilterExpression(
                    filter=Filter(
                        field_name='customEvent:micro_step',
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value='dati_utente'
                        )
                    )
                ),
                FilterExpression(
                    filter=Filter(
                        field_name='customEvent:operazione',
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value='weborder'
                        )
                    )
                ),
                FilterExpression(
                    not_expression=FilterExpression(
                        filter=Filter(
                            field_name='fullPageUrl',
                            string_filter=Filter.StringFilter(
                                match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                                value='pp.'
                            )
                        )
                    )
                )
            ]
        )
    )


def commodity_type_filter(commodity_type: str = ['dual', 'luce', 'gas']) -> FilterExpression:
    """
    Filtro per commodity dual
    """
    return FilterExpression(
        and_group=FilterExpressionList(
            expressions=[
                FilterExpression(
                    filter=Filter(
                        field_name='customEvent:commodity',
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value = commodity_type
                        )
                    )
                )
            ]
        )
    )
