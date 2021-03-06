#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 19 13:23:36 2019

@author: rdamseh
"""

import networkx as nx

class WritePajek:
    
    def __init__(self, path, name, graph):

        self.path=path
        self.name=name

        graph=self.__stringizer(graph.copy())
        
        nx.write_pajek(graph, self.path+self.name)
        
    def __stringizer(self, g):
        
        test_id=g.GetNodes()[0]
        attr_to_stringize=['pos', 'r', 'd', 'type', 'branch', 'flow', 'pressure', 
                           'velocity', 'po2', 'so2', 'velocity', 
                           'source', 'sink', 'inflow', 'outflow', 'vol', 'area']
        
        for i in attr_to_stringize:
            try:
                if type(g.node[test_id][i]) is str:
                    attr_to_stringize.remove(i)
            except:
                pass

        for j in attr_to_stringize:
            
            for i in g.GetNodes():
                
                try:
                    g.node[i][j]=str(g.node[i][j])
                except:
                    pass
        return g
    
        for e in g.GetEdges():
            for j in attr_to_stringize:
                try:
                    g[e[0]][e[1]]=str(g[e[0]][e[1]])
                except:
                    pass
        return g    

                
    def Update(self): pass