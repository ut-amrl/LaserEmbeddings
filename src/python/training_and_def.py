#!/usr/bin/env python2

# -*- coding: utf-8 -*-
"""
Created on Tue Mar  6 17:35:43 2018

@author: samer

"""

#TODO: refactor into separate files for each network, and
#      separate files for nominal training versus special cases / debugging

from __future__ import print_function

import rospy
#from std_msgs.msg import string
from std_msgs.msg import String


import os
#import copy
import torch
import shutil
import argparse
import numpy as np
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import convert_png_to_numpy as cptn
import torch.backends.cudnn as cudnn

from scipy import spatial
from visdom import Visdom
from torch.autograd import Variable
from torchvision import datasets, transforms
from sklearn.decomposition import PCA, KernelPCA

import training_and_def_net3 as net3


#NOTE: EXPERIMENTAL PARAMS:

# input shape / type (1d, 2d flat, 2d perdiodic rotation)

# input size (downsampling rate)

# input richness (single scan vs history of scans)

# input noising (yes / no / how)

# network structure (num layers, convolution vs max pooling vs fully connected, etc.)

# dimensionality of output (embedding)

# gradient descent methods (SGD, ADOM, Momentum, etc)

# training hacks (dropout, batch size)

# hyperparameters (learning rate, biases, initialization)

# activation function (ReLU, tanh, sigmoid, etc.)

# training example selection (selection of pairs, shuffling, presentation order, etc.)
    # regular (time-based)
    # noised
    # objectified
# loss function (L-2 norm, cosine distance, etc.)

# 

#TODO: improve training data selection

#TODO: LIST OF EXPERIMENTS

#embeddings_database = []

class Net3(nn.Module): #NOTE: 
  def __init__(self):
    super(Net3, self).__init__()

    # non-square kernel 
    self.conv1_1 = nn.Conv2d(1, 1, (1, 3), 1, (0, 1))
    self.conv1_2 = nn.Conv2d(1, 1, (1, 5), 1, (0, 2))
    self.conv1_3 = nn.Conv2d(1, 1, (1, 9), 1, (0, 4))
    self.conv1_4 = nn.Conv2d(1, 1, (1, 17), 1, (0, 8))
    self.conv1_5 = nn.Conv2d(1, 1, (1, 33), 1, (0, 16))
    self.conv1_6 = nn.Conv2d(1, 1, (1, 65), 1, (0, 32))
    self.conv1_7 = nn.Conv2d(1, 1, (1, 129), 1, (0, 64))
    self.conv2 = nn.Conv2d(14, 8, 11, 1, 1)
    self.conv3 = nn.Conv2d(8, 16, 5, 1, 1)
    self.fc1 = nn.Linear(16 * 30 * 30, 256)
    self.fc2 = nn.Linear(256, 128)
    self.fc3 = nn.Linear(128, 64)
    #self.fc4 = nn.Linear(64, 32)
    #self.fc5 = nn.Linear(32, 64)
    self.fc6 = nn.Linear(64, 128)
    self.fc7 = nn.Linear(128, 256)

  def forward(self, emb):
    #print(emb.shape)
    #x = F.relu(self.fc5(emb))
    x = F.relu(self.fc6(emb))
    #print(x.shape)
    x = F.tanh(self.fc7(x))

    return x

  def num_flat_features(self, x):
    size = x.size()[1:]  # all dimensions except the batch dimension
    num_features = 1
    for s in size:
      num_features *= s
    return num_features

############################## TRIPLET NET ##############################

class TripletNet(nn.Module):
  def __init__(self, embeddingnet):
    super(TripletNet, self).__init__()
    self.embeddingnet = embeddingnet

  def forward(self, emb):
    recreation = self.embeddingnet(emb)
    return recreation


############################## LOADING STUFF ##############################

def loadNetwork():
  model = net3.Net3()
  model = model.cuda()
  tnet = net3.TripletNet(model)
  tnet = tnet.cuda()

  checkpoint_to_load = 'model_checkpoints/current/most_recent.pth.tar'

  if os.path.isfile(checkpoint_to_load):
    print("=> loading checkpoint '{}'".format(checkpoint_to_load))
    checkpoint = torch.load(checkpoint_to_load)
    tnet.load_state_dict(checkpoint['state_dict'])
    print("=> loaded checkpoint '{}' (epoch {})"
            .format(checkpoint_to_load, checkpoint['epoch']))
  else:
    print("=> no checkpoint found at '{}'".format(checkpoint_to_load))

  n_parameters = sum([p.data.nelement() for p in tnet.parameters()])
  print('  + Number of params: {}'.format(n_parameters))

  return tnet

def loadEmbeddingDatabase():
  database_set = cptn.SpecialQuerySet()
  global dn, dr
  dn, dr = database_set.getSpecificItem(0)
  global embeddings_database
  embeddings_database = generateEmbeddings(database_set)

############################## VISUALIZATION ##############################

class VisdomLinePlotter(object):
  # Plots to Visdom
  def __init__(self, env_name='main'):
    self.viz = Visdom()
    self.env = env_name
    self.plots = {}
  def plot(self, var_name, split_name, x, y):
    if var_name not in self.plots:
      self.plots[var_name] = self.viz.line(X=np.array([x,x]), Y=np.array([y,y]), env=self.env, opts=dict(
          legend=[split_name],
          title=var_name,
          xlabel='Epochs',
          ylabel=var_name
      ))
    else:
      self.viz.updateTrace(X=np.array([x]), Y=np.array([y]), env=self.env, win=self.plots[var_name], name=split_name)

def visEmbeddingDecoder():
  #embeddings = []
  #infile = open('embeddings.txt', 'r')
  #for line in infile:
  #  embedding_list = line.split()
  #  embedding = np.array(embedding_list, dtype=np.float32)
  #  embeddings.append(embedding)

  
  k = 10
  interpolated_embeddings = []
  last = embeddings_database[-1]
  for i in range(0, len(embeddings_database)-200, 200):
    embedding_diff = np.asarray(embeddings_database[i+200]) - np.asarray(embeddings_database[i])
    last = np.asarray(embeddings_database[i+200])
    for j in range(k):
      interpolated_embeddings.append(np.asarray(embeddings_database[i]) + float(j)/float(k) * embedding_diff)
  interpolated_embeddings.append(last)

  model = Net3()
  model = model.cuda()
  tnet = TripletNet(model)
  tnet = tnet.cuda()

  resume = True
  checkpoint_to_load = 'model_checkpoints/current/most_recent.pth.tar'

  # optionally resume from a checkpoint
  if resume:
    if os.path.isfile(checkpoint_to_load):
      print("=> loading checkpoint '{}'".format(checkpoint_to_load))
      checkpoint = torch.load(checkpoint_to_load)
      tnet.load_state_dict(checkpoint['state_dict'])
      print("=> loaded checkpoint '{}' (epoch {})"
              .format(checkpoint_to_load, checkpoint['epoch']))
    else:
      print("=> no checkpoint found at '{}'".format(checkpoint_to_load))

  n_parameters = sum([p.data.nelement() for p in tnet.parameters()])
  print('  + Number of params: {}'.format(n_parameters))

  recreations = []
  print(len(interpolated_embeddings))
  for emb in interpolated_embeddings:
  #for emb in embeddings:
    # turn training off
    tnet.eval()
    emb = np.asarray(emb, dtype=np.float32)
    emb = Variable(torch.from_numpy(emb))
    emb = emb.cuda()
    recreation = tnet(emb)
    recreations.append(recreation)

  outfile = open('recreations.txt', 'a')
  for i in range(len(recreations)):
    recreation = recreations[i]
    recreation = recreation.cpu()
    recreation = recreation.data.numpy().tolist()
    for i in range(len(recreation)):
      outfile.write(str(recreation[i]))
      outfile.write(" ")
    outfile.write("\n")

  outfile.close();

######################### GENERATE EMBEDDINGS #########################

def writeEmbeddings(embeddings):
  outfile = open('embeddings.txt', 'a')
  for i in range(len(embeddings)):
    for j in range(len(embeddings[i])):
      outfile.write(str(embeddings[i][j]))
      outfile.write(" ")
    outfile.write("\n")
  outfile.close();

def generateEmbeddings(test_set):

  #rawoutfile = open('scansasimages.txt', 'a')
  #ni, r = test_set.getSpecificItem(0)
  #ds_scan = n[0, 0,:]
  #print(ds_scan)

  # switch to evaluation mode
  tnet.eval()

  embeddings = []
  #for idx in range(0, len(test_set), 300):
  for idx in range(len(test_set)):

    if idx % 100 == 0:
      print(str(idx)+"/"+str(len(test_set)))

    data1n, data1r = test_set.getSpecificItem(idx)
    data2n, data2r = test_set.getSpecificItem(0)
    data3n, data3r = test_set.getSpecificItem(0)
    
    data1n = data1n.unsqueeze(0)
    data2n = data2n.unsqueeze(0)
    data3n = data3n.unsqueeze(0)
    data1r = data1r.unsqueeze(0)
    data2r = data2r.unsqueeze(0)
    data3r = data3r.unsqueeze(0)
    #print("scan in image form \n")
    #print(data1n[0, 0, 0, :].tolist())
    #rawscanimg = data1n[0, 0, 0, :].tolist()
    #for i in range(len(data1n[0, 0, 0, :].tolist())):
    #  rawoutfile.write(str(rawscanimg[i]))
    #  rawoutfile.write(" ")
    #rawoutfile.write("\n")

    data1n, data2n, data3n = Variable(data1n), Variable(data2n), Variable(data3n)
    data1r, data2r, data3r = Variable(data1r), Variable(data2r), Variable(data3r)
    data1n = data1n.cuda()
    data2n = data2n.cuda()
    data3n = data3n.cuda()
    data1r = data1r.cuda()
    data2r = data2r.cuda()
    data3r = data3r.cuda()

    # compute output
    # NOTE: reversing order of data because I'm not confident in changing down stream eval
    _, _, embedded_1, _, _, _ = tnet(data1n, data2n, data3n, data1r, data2r, data3r)

    # write embeddings to text file
    embedded_1 = embedded_1.cpu()
    embedded_1 = embedded_1.data.numpy().tolist()
    embedded_1 = embedded_1[0]
    embeddings.append(embedded_1)

  return embeddings

############################## DISTANCE ##############################

def computeSubspaceDistance(a, b, basis_vectors, weights):
  diff = a - b
  subspace_distance = 0
  for i in range(len(weights)):
    new_dist = abs(np.dot(diff, basis_vectors[i, :]) / np.linalg.norm(basis_vectors[i, :]))
    subspace_distance = subspace_distance + weights[i] * new_dist
  return subspace_distance

############################## TOP K ##############################

def KNNOnEmbeddings(database, queries):
    K = 300

    query_results = []
    for idx in range(len(queries)):
      print(idx)
      x = queries[idx]
      query_result = []
      for idt in range(len(database)):
        if idt % 1000 == 0:
          print(str(idt)+"/"+str(len(database)))
        y = database[idt]
        y = np.asarray(y)
        dissimilarity = spatial.distance.cosine(y, x)
        #dissimilarity = np.linalg.norm(y - x)
        single_scan = []
        if len(query_result) < K:
          single_scan.append(idt)
          single_scan.append(dissimilarity)
          query_result.append(single_scan)
        else:
          if dissimilarity < query_result[0][1]:
            single_scan.append(idt)
            single_scan.append(dissimilarity)
            query_result[0] = single_scan
            # reverse sort based on similarity
            query_result.sort(key = lambda k: (k[1]), reverse=True)

      query_results.append(query_result)

    return query_results

def SubspaceKNNOnEmbeddings(database, queries, basis_vectors, weights):
    K = 10

    query_results = []
    for idx in range(len(queries)):
      print(idx)
      x = queries[idx]
      query_result = []
      for idt in range(len(database)):
        if idt % 1000 == 0:
          print(idt)
        y = database[idt]
        y = np.asarray(y)
        dissimilarity = computeSubspaceDistance(x, y, basis_vectors, weights)
        single_scan = []
        if len(query_result) < K:
          single_scan.append(idt)
          single_scan.append(dissimilarity)
          query_result.append(single_scan)
        else:
          if dissimilarity < query_result[0][1]:
            single_scan.append(idt)
            single_scan.append(dissimilarity)
            query_result[0] = single_scan
            # reverse sort based on similarity
            query_result.sort(key = lambda k: (k[1]), reverse=True)

      query_results.append(query_result)

    return query_results

############################## MAIN ##############################

def simpleQuery(query_embeddings):

  npqueryembed = np.zeros((len(query_embeddings), len(query_embeddings[0])))

  final_query_embeddings = []
  embedding_sum = np.zeros(len(query_embeddings[0]))
  print("number of embedding examples: "+str(len(query_embeddings)))
  for i in range(len(query_embeddings)):
    embedding_sum = embedding_sum + np.asarray(query_embeddings[i])
    npqueryembed[i, :] = np.asarray(query_embeddings[i])
  embedding_mean = np.true_divide(embedding_sum, len(query_embeddings))
  final_query_embeddings.append(embedding_mean)

  #print(embeddings_database[0])
  #print(final_query_embeddings[0])

  query_results = KNNOnEmbeddings(embeddings_database, final_query_embeddings)

  for i in range(len(query_results)):
    print("QUERY: "+str(i))
    for j in range(len(query_results[i])):
      print(query_results[i][j])


def advancedQuery():


  print("finding query mean")
  print(len(query_embeddings))
  print(len(query_embeddings[0]))

  npqueryembed = np.zeros((len(query_embeddings), len(query_embeddings[0])))

  final_query_embeddings = []
  embedding_sum = np.zeros(len(query_embeddings[0]))
  print("number of embedding examples: "+str(len(query_embeddings)))
  for i in range(len(query_embeddings)):
    embedding_sum = embedding_sum + np.asarray(query_embeddings[i])
    npqueryembed[i, :] = np.asarray(query_embeddings[i])
  embedding_mean = np.true_divide(embedding_sum, len(query_embeddings))
  final_query_embeddings.append(embedding_mean)


  kappa = 5
  #basis_vectors = np.zeros((len(final_query_embeddings[0]), 5))
  basis_vectors = np.zeros((5, len(final_query_embeddings[0])))
  weights = np.ones(kappa)
  #TODO: use xplained variance to weight each dimension in subspace distance calculation?
  #weights = np.zeros(kappa)
  if len(query_embeddings) > 1:
    print("PCA")
    pca = PCA()
    pca.fit(npqueryembed)
    components = pca.components_
    print(components)
    print(components.shape)
    for i in range(kappa):
      basis_vectors[i, :] = components[len(final_query_embeddings[0]) - 1 - i, :]

  print("KNN")

  #query_results = KNNOnEmbeddings(database_embeddings, final_query_embeddings)
  query_results = SubspaceKNNOnEmbeddings(database_embeddings, final_query_embeddings, basis_vectors, weights)

  for i in range(len(query_results)):
    print("QUERY: "+str(i))
    for j in range(len(query_results[i])):
      print(query_results[i][j])

def queryCallback(msg):
  rospy.loginfo(rospy.get_caller_id() + "I heard %s", msg.data)
  if msg.data == "FO":
    query_set = cptn.FeatureOnlyTestSet()
    #qn, qr = query_set.getSpecificItem(0)
    #d_scan = dn[0, 0, :]
    #q_scan = qn[0, 0, :]
    #print("difference")
    #print(d_scan - q_scan)
    query_embeddings = generateEmbeddings(query_set)
    simpleQuery(query_embeddings)
  elif msg.data == "MC":
    query_set = cptn.MonteCarloTestSet()
    query_embeddings = generateEmbeddings(query_set)
    advancedQuery()


def main():
  global tnet 
  tnet = loadNetwork()
  loadEmbeddingDatabase()

  #NOTE: uncomment to turn on embedding interpolation - saved in recreations.txt
  visEmbeddingDecoder()

  print("database size:")
  print(len(embeddings_database))

  rospy.init_node('QueryManager', anonymous=True)
  rospy.Subscriber("DataDirectory", String, queryCallback)

  print("Ready to answer queries")

  rospy.spin()

if __name__ == '__main__':
  main()
  print ("donzo")
