import { useCallback } from 'react';
import dagre from 'dagre';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 220;
const NODE_HEIGHT = 180;

export function useAutoLayout() {
  const layoutNodes = useCallback((nodes: Node[], edges: Edge[], direction: 'TB' | 'LR' = 'TB'): Node[] => {
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: direction, nodesep: 80, ranksep: 120, marginx: 40, marginy: 40 });

    nodes.forEach(node => {
      g.setNode(node.id, { width: NODE_WIDTH, height: node.data?.layoutHeight || NODE_HEIGHT });
    });

    edges.forEach(edge => {
      g.setEdge(edge.source, edge.target);
    });

    dagre.layout(g);

    const layouted = nodes.map(node => {
      const dagreNode = g.node(node.id);
      if (!dagreNode) return node;
      return {
        ...node,
        position: {
          x: dagreNode.x - NODE_WIDTH / 2,
          y: dagreNode.y - (node.data?.layoutHeight || NODE_HEIGHT) / 2,
        },
      };
    });

    return layouted;
  }, []);

  return { layoutNodes };
}
