# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

"""
tf2onnx.rewriter - rewrite tensorflow subgraph to onnx ThresholdedRelu op
"""

from tf2onnx.graph_matcher import OpTypePattern, GraphMatcher
from tf2onnx.rewriter.leakyrelu_rewriter import _find_edge_name_between_nodes


# pylint: disable=missing-docstring


def rewrite_thresholded_relu(g, ops):
    if g.opset < 10:
        return ops

    pattern = \
        OpTypePattern('Mul', name='mul', inputs=[
            OpTypePattern('Cast', name='cast', inputs=[
                OpTypePattern('Greater', name='greater', inputs=[
                    OpTypePattern('*', name='greater_input'),
                    OpTypePattern('Const', name='theta')
                ])
            ]),
            OpTypePattern('*', name='mul_input')
        ])
    matcher = GraphMatcher(pattern, allow_reorder=True)
    match_results = list(matcher.match_ops(ops))

    for match in match_results:
        greater_node = match.get_op('greater')
        greater_input_node = match.get_op('greater_input')
        mul_node = match.get_op("mul")
        mul_input_node = match.get_op('mul_input')
        cast_node = match.get_op('cast')

        greater_input_edge_name = _find_edge_name_between_nodes(greater_input_node, greater_node)
        mul_input_edge_name = _find_edge_name_between_nodes(mul_input_node, mul_node)
        if greater_input_edge_name == mul_input_edge_name:
            theta = match.get_op('theta').get_tensor_value()
            # check disabled for now, tf requires theta to be non-negative, while onnx does not
            # if theta < 0:
            #     continue
            thresholded_relu = g.make_node("ThresholdedRelu", inputs=[mul_input_edge_name], attr={"alpha": theta},
                                    shapes=[g.get_shape(mul_node.output[0])], dtypes=[g.get_dtype(mul_node.output[0])])
            ops.remove(greater_node)
            ops.remove(cast_node)
            ops.remove(mul_node)
            ops.append(thresholded_relu)
            g.replace_all_inputs(ops, mul_node.output[0], thresholded_relu.output[0])
    return ops

