#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  5 11:03:31 2019

@author: rdamseh
"""
from VascGraph.Tools.CalcTools import *
from VascGraph.Skeletonize import BaseGraph
import scipy as sp

class ContractGraph(BaseGraph):
       
    
    def __init__(self, Graph=None):
        
        if Graph is not None:
            self.Graph=Graph 

    # private    
    def __CheckGraph(self):
 
        '''
        Check the graph before contraction to obtain 
        the potential nodes to be processed
        '''
        
        #remove single nodes
        NodesToRemove=[i for i in self.Graph.GetNodes() if len(self.Graph.GetNeighbors(i))==0]
        self.Graph.remove_nodes_from(NodesToRemove)

        # obtain info
        self.Nodes=np.array(self.Graph.GetNodes())
        self.NNodes=len(self.Nodes)
        self.NodesPos=np.array([self.Graph.node[i]['pos'] for i in self.Nodes])

        self.Neighbors=[self.Graph.GetNeighbors(i) for i in self.Nodes]
        self.NeighborsPos=[np.array([self.Graph.node[i]['pos'] for i in j]) for j in self.Neighbors]
        
        self.MedialValues=np.array([self.Graph.node[i]['r'] for i in self.Nodes])
        self.Degree=[len(i) for i in self.Neighbors]


        # check if a nodes is skeletal
        if self.DegreeThreshold is not None:
            CheckNeighbors=[len(i)>1 for i in self.Neighbors]  # True in nbrs > 1
            CheckDegree=IsSklNodes(self.NodesPos, self.NeighborsPos, self.DegreeThreshold) # true if skeleton
            self.SkeletalMask=np.logical_and(CheckNeighbors, CheckDegree) # true if skeleton, false otherwise
        else:
            self.SkeletalMask=np.array([False]*self.Graph.number_of_nodes())
            
        #nodes_to_process & skl nodes
        self.NodesToProcess=self.Nodes[self.SkeletalMask==False]
        self.PosToProcess=self.NodesPos[self.SkeletalMask==False]
    
        self.SkeletalNodes=self.Nodes[self.SkeletalMask]


    def __CheckIter(self):
            '''
            check if to continue iteration or not, based on the area of polygns
            '''            
            #find polygons
            cyc=nx.cycle_basis(self.Graph)
            
            Area=0
            for l in range(10):
                if l>2:
                    Polygons=(k for k in cyc if len(k)==l)  
                    Pos=np.array([[self.Graph.node[j]['pos'] for j in i]  for i in Polygons])
                    Area+=np.sum(CycleAreaAll(Pos))

            Check=Area>self.AreaThreshold
            return Check, Area


    def __ApplyContraction(self, save_info=False, update_positions=True):
    
        print('Solving linear system ...')
        # obtain nodes indices in order      
        NodesOrderedInd=range(self.NNodes)
        NodesIndices=dict(zip(self.Nodes, NodesOrderedInd)) 
        
        # used to fill 'A' matrix
        NeighborsMat=np.array(self.Neighbors)
        NeighborsMat, MaskMat=numpy_fill(NeighborsMat, self.Degree) 
           
        def GetDistMat(Pos, NbrsPos, Degree):
            
            NbrsPos=np.array(NbrsPos)
            NbrsPos, MaskMat=numpy_fill(NbrsPos, Degree, 3) # padded numpy array  
            Dist0=np.linalg.norm(Pos[:,None]-NbrsPos, axis=2)*MaskMat #*nodes_degree
            Dist1=np.sum(Dist0, axis=1)
            Dist1[Dist1==0]=1
            
            return Dist0/Dist1[:,None]          
            
        def GetMedMat(NeighborsMat, MaskMat, MedialValues, NodesIndices):
                   
            NeighborsIndices=[NodesIndices[i] for i in NeighborsMat[MaskMat].astype(int)]      
            Med0=np.zeros_like(NeighborsMat)
            Med0[MaskMat]=MedialValues[NeighborsIndices] # fill mediality values
            Med1=np.sum(Med0, axis=1)
            
            return Med0/Med1[:,None]


        def GetMedMat_new(NeighborsMat, MaskMat, MedialValues, NodesIndices):
                   
            NeighborsIndices=[NodesIndices[i] for i in NeighborsMat[MaskMat].astype(int)]      
            Med0=np.zeros_like(NeighborsMat)
            Med0[MaskMat]=MedialValues[NeighborsIndices] # fill mediality values
            Med0=Med0-np.min(Med0, axis=1)
            
            Med1=np.sum(Med0, axis=1)
            Med1[Med1==0]=1
            
            return Med0/Med1[:,None]
        
        def GetAMat(NeighborsMat, MaskMat, NodesIndices, NNodes,
                    DistValues, MedValues, SpeedValues,
                    DistParam, MedParam):
            
            # build sparse matrices A and B       
            A=sp.sparse.lil_matrix((NNodes*3, NNodes))
 
            # insert DistVlaues              
            Ind1=np.zeros_like(NeighborsMat)          
            Ind1=Ind1+np.array(range(NNodes))[:,None]
            Ind1=Ind1[MaskMat].astype(int) 
            Ind2=[NodesIndices[i] for i in NeighborsMat[MaskMat].astype(int)]               
            A[Ind1.tolist() ,Ind2]=DistMat[MaskMat]*DistParam        
            A[NodesOrderedInd ,NodesOrderedInd]=-1*DistParam         
     
           # insert MedValues
            Ind11=Ind1+NNodes
            Ind22=np.array(NodesOrderedInd)+NNodes            
            A[Ind11.tolist(),Ind2]=MedValues*MedParam
            A[Ind22.tolist(), NodesOrderedInd]=-1*MedParam        
        
            # insert speed values
            Ind111=np.array(NodesOrderedInd)+2*NNodes
            A[Ind111.tolist(), NodesOrderedInd]=SpeedValues
            
            return A.tocoo()
  
        def GetBMat(Pos, SpeedValues):
            B=np.vstack([np.zeros_like(Pos), np.zeros_like(Pos), 
                         Pos*np.array([SpeedValues,SpeedValues,SpeedValues]).T]) # b matrix
            return B
            
    
        def Solve(A, B):
            px = sp.sparse.linalg.lsqr(A, B[:,0], atol=1e-06, btol=1e-06)[0] 
            py = sp.sparse.linalg.lsqr(A, B[:,1], atol=1e-06, btol=1e-06)[0]
            pz = sp.sparse.linalg.lsqr(A, B[:,2], atol=1e-06, btol=1e-06)[0]
            NewPos=np.array([px, py, pz]).T
            
            return NewPos
             
        # laplacian operators / obtain weights  
        DistMat=GetDistMat(self.NodesPos, self.NeighborsPos, self.Degree)      
        MedMat=GetMedMat(NeighborsMat, MaskMat, self.MedialValues, NodesIndices)
               
        if save_info:
            self.DistMat=DistMat
            self.MedMat=MedMat
            
        DistValues=DistMat[MaskMat] 
        MedValues=MedMat[MaskMat]     
        SpeedValues=(self.SkeletalMask==False)*self.SpeedParam+(self.SkeletalMask)*10*self.SpeedParam # skl nodes will move at lower speed
        
        # build A and B
        A=GetAMat(NeighborsMat, MaskMat, NodesIndices, self.NNodes,
                    DistValues, MedValues, SpeedValues, 
                    self.DistParam, self.MedParam)
        
        B= GetBMat(self.NodesPos, SpeedValues)
 
        # solve
        NewPos=Solve(A, B)
    
        #update the graph
        if update_positions:
            for ind, i in enumerate(self.Nodes):
                self.Graph.node[i]['pos']=NewPos[ind]


    def __ContractGraph(self):            
        
        self.Iteration = 1
        self.AreaThreshold=0
        Check=True 
        
        while Check:
                    
            # setup area threshold
            if self.Iteration==1:
#                Check, Area=self.__CheckIter()
#                print('Area: '+str(Area))
                self.AreaThreshold=self.Graph.Area*self.StopParam 
                print('Area: '+str(self.Graph.Area))
                
            # examin skeletal nodes and get info
            self.__CheckGraph() 
            # apply contraction
            self.__ApplyContraction()             
            # cluster and update topology
            self._BaseGraph__UpdateTopology(resolution=self.ClusteringResolution)

            if self.Iteration>=self.NFreeIteration:
                Check, Area=self.__CheckIter()
                self.Graph.Area=Area
                if not Check:
                    print('Converged! Cycles Area is less than '+str(self.AreaThreshold))
                else:
                    print('Area: '+str(Area))
  
            self.Iteration+=1
       

    def __ContractGraphOneStep(self, update_positions=False):            
        
        try:
            self.Iteration += 1
        except:
            self.Iteration = 1
        
        self.AreaThreshold=0
        
        # setup area threshold
        if self.Iteration==1:
#                Check, Area=self.__CheckIter()
#                print('Area: '+str(Area))
            self.AreaThreshold=self.Graph.Area*self.StopParam 
            print('Area: '+str(self.Graph.Area))
            
        # examin skeletal nodes and get info
        self.__CheckGraph() 
        # apply contraction
        self.__ApplyContraction(save_info=True, update_positions=update_positions)   

         
    def Update(self, DistParam=1,
                     MedParam=1,
                     SpeedParam=.1, 
                     DegreeThreshold=None,
                     NFreeIteration=1,
                     ClusteringResolution=1.0,
                     StopParam=.01):
        
        self.DistParam=DistParam
        self.MedParam=MedParam
        self.SpeedParam=SpeedParam 
        self.DegreeThreshold=DegreeThreshold
        self.NFreeIteration=NFreeIteration
        self.ClusteringResolution=ClusteringResolution
        self.StopParam=StopParam       
        self.__ContractGraph()
  

    def UpdateOneStep(self, DistParam=1,
                     MedParam=1,
                     SpeedParam=.1, 
                     DegreeThreshold=None,
                     NFreeIteration=1,
                     ClusteringResolution=1.0,
                     StopParam=.01, 
                     update_positions=False):
        
        self.DistParam=DistParam
        self.MedParam=MedParam
        self.SpeedParam=SpeedParam 
        self.DegreeThreshold=DegreeThreshold
        self.NFreeIteration=NFreeIteration
        self.ClusteringResolution=ClusteringResolution
        self.StopParam=StopParam 
        
        self.__ContractGraphOneStep(update_positions=update_positions)

    def UpdateTopologyOneStep(self):
        
        # cluster and update topology
        self._BaseGraph__UpdateTopology(resolution=self.ClusteringResolution)

      
    def GetFlowVectors(self, which='distance'):
        
        '''
        This function obtain the vector field generated from applying the lablacian operator
        during the contraction process
        '''
        g=self.Graph.copy()
        pos=np.array(g.GetNodesPos())
        npos=self.NeighborsPos
 
        if which=='distance':
            mat=self.DistMat
        else:
            mat=self.MedMat
            
        npos=np.array(npos)
        npos,_ =numpy_fill(npos, self.Degree, 3)
        sum_vector=np.sum(mat[:,:,None]*npos, axis=1)
        
        sum_vector=np.array([j-i for i,j in zip(pos, sum_vector)])

        x, y, z = pos[:,0], pos[:,1], pos[:,2]
        u, v, w = sum_vector[:,0], sum_vector[:,1], sum_vector[:,2]
    
        return x,y,z,u,v,w

        
    def GetOutput(self):
        return self.Graph          


if __name__=='__main__':
    
    pass
            
  
   