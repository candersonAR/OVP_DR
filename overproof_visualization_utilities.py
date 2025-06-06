
import json
import jinja2
from ar_analytics import ArUtils

from skill_framework import SkillVisualization
from skill_framework.layouts import wire_layout

from ar_analytics.defaults import get_table_layout_vars
from ar_analytics.helpers.df_meta_util import apply_metadata_to_layout_element

'''
Overwritten for overproof's dimension breakout skill to include the general footnote.
'''
def find_footnote(footnotes, df, general_footnote=None):
    footnotes = footnotes or {}
    for col in df.columns:
        if col in footnotes:
            dim_note = footnotes.get(col)
            if general_footnote:
                return dim_note + "\n" + general_footnote
            return dim_note
    return general_footnote

'''
Overwritten for overproof's dimension breakout skill to include the general footnote.
'''
def render_layout(tables, title, subtitle, insights_dfs, warnings, footnotes, general_footnote, max_prompt, insight_prompt, viz_layout):
    facts = []
    for i_df in insights_dfs:
        facts.append(i_df.to_dict(orient='records'))

    insight_template = jinja2.Template(insight_prompt).render(**{"facts": facts})
    max_response_prompt = jinja2.Template(max_prompt).render(**{"facts": facts})

    # adding insights
    ar_utils = ArUtils()
    insights = ar_utils.get_llm_response(insight_template)
    viz_list = []
    export_data = {}

    general_vars = {"headline": title if title else "Total",
                    "sub_headline": subtitle or "Breakout Analysis",
                    "hide_growth_warning": False if warnings else True,
                    "exec_summary": insights if insights else "No Insights.",
                    "warning": warnings}

    viz_layout = json.loads(viz_layout)

    for name, table in tables.items():
        export_data[name] = table
        dim_note = find_footnote(footnotes, table, general_footnote)
        hide_footer = False if dim_note else True
        table_vars = get_table_layout_vars(table)
        table_vars["hide_footer"] = hide_footer
        table_vars["footer"] = f"*{dim_note.strip()}" if dim_note else "No additional info."
        meta_viz_layout = apply_metadata_to_layout_element(viz_layout, "DataTable0",
                                                           {"sourceDataframeId": table.max_metadata.get_id()})
        rendered = wire_layout(meta_viz_layout, {**general_vars, **table_vars})
        viz_list.append(SkillVisualization(title=name, layout=rendered))

    return viz_list, insights, max_response_prompt, export_data
