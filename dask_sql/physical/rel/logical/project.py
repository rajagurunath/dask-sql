from typing import Dict

import dask.dataframe as dd

from dask_sql.physical.rex import RexConverter
from dask_sql.physical.rex.core.input_ref import RexInputRefPlugin
from dask_sql.physical.rel.base import BaseRelPlugin
from dask_sql.datacontainer import DataContainer
from dask_sql.java import get_java_class


class LogicalProjectPlugin(BaseRelPlugin):
    """
    A LogicalProject is used to
    (a) apply expressions to the columns and
    (b) only select a subset of the columns
    """

    class_name = "org.apache.calcite.rel.logical.LogicalProject"

    def convert(
        self, rel: "org.apache.calcite.rel.RelNode", tables: Dict[str, dd.DataFrame]
    ) -> dd.DataFrame:
        # Get the input of the previous step
        (dc,) = self.assert_inputs(rel, 1, tables)

        df = dc.df
        cc = dc.column_container

        # Collect all (new) columns
        named_projects = rel.getNamedProjects()

        column_names = []
        new_columns = {}
        for expr, key in named_projects:
            key = str(key)
            column_names.append(key)

            # shortcut: if we have a column already, there is no need to re-assign it again
            # this is only the case if the expr is a RexInputRef
            if get_java_class(expr) == RexInputRefPlugin.class_name:
                index = expr.getIndex()
                backend_column_name = cc.get_backend_by_frontend_index(index)
                cc = cc.add(key, backend_column_name)
            else:
                new_columns[key] = RexConverter.convert(expr, dc=dc)
                cc = cc.add(key, key)

        # Actually add the new columns
        if new_columns:
            df = df.assign(**new_columns)

        # Make sure the order is correct
        cc = cc.limit_to(column_names)

        cc = self.fix_column_to_row_type(cc, rel.getRowType())
        return DataContainer(df, cc)
