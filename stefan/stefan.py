# -*- coding: utf-8 -*-
"""
Created on Wed Oct 19 21:22:44 2016

@author: Stefan Setyadi
"""

import numpy as np
import pandas as pd
import time
from sklearn.metrics import mean_squared_error as mse, mean_absolute_error as mae
from sklearn.metrics import pairwise_distances as distance

def cos_sim(matrix, epsilon=1e-9):
    sim = matrix.T.dot(matrix) + epsilon
    norms = np.array([np.sqrt(np.diagonal(sim))])
    return (sim/norms/norms.T)
    
def correlation_sim(matrix):
    return np.corrcoef(matrix.T)
    

def predict_wsum(ratings,similarity):
    ## improved
    nonzero_pos = ratings.nonzero()
    if(np.count_nonzero(nonzero_pos)==0):
        return 0
    else:    
        return ratings.dot(similarity)/ np.sum(similarity.take(nonzero_pos))
    ## normal
    #return ratings.dot(similarity)/ np.sum(similarity)
    
def predict_topk(ratings,similarity,k):
    pred = np.zeros(ratings.shape).astype(np.float32)
    topk = get_topk_pos(similarity,k)
    for i in range(len(topk)):
        #starttime = time.time()
        new_sim = similarity[i,topk[i]]
        for j in range(len(ratings)):
            new_rating = ratings[j,topk[i]]
            pred[j,i] = predict_wsum(new_rating,new_sim)
        #pred[:,i] = predict_wsum(ratings[:,topk[i]],new_sim)
        #print("pred {}: {}".format(i,time.time()-starttime))
    return pred
    
def get_score(pred, actual):
    pred = pred[actual.nonzero()].flatten()
    actual = actual[actual.nonzero()].flatten()
    mseResult = mse(pred,actual)
    maeResult = mae(pred,actual)
    print("MSE = {}, MAE = {}".format(mseResult,maeResult))
    return mseResult    
    
def loadDF(pathName,name,cut_last=True):
    temp_df = pd.read_csv(pathName, sep=',', names=name)
    if(cut_last):
        temp_df.drop(name[-1:], axis=1, inplace=True)    
    return temp_df

def get_topk_pos(similarity,k):
    ## argpartition will return topk but not ordered
    return np.argpartition(-similarity,(0,k))[:,0:k]

def topk_mse(train,test,item_sim,k):
    test_mse = []
    train_mse = []
    print("starting top-k MSE")
    np.fill_diagonal(item_sim,0)
    for i in k:
        starttime = time.time()
        prediction = predict_topk(train,item_sim,i)
        #print(prediction[:4,:4])
        train_mse.append(get_score(prediction,train))
        test_mse.append(get_score(prediction,test))
        print("k={}, time={}".format(i,time.time()-starttime))
    print("Train\t: {}".format(train_mse))
    print("Test\t: {}".format(test_mse))

def topk_to_file(writePathName, similarity,k):
    writeStr = []
    np.fill_diagonal(similarity,0)
    top10 = np.argpartition(-similarity,[i for i in range(k+1)])[:,0:k] # without the item itself
    for i in range(len(top10)):
        writeStr.append("{}:{}".format(index2_id[i],
                        ",".join(["{}={}".format(index2_id[j],similarity[i,j]) for j in top10[i]])))
    writeStr = "\n".join(writeStr)
    with open(writePathName, 'w') as writeFile:
        writeFile.write(writeStr)
        
def load_kc_sim(pathName,id_to_idx,eps=1e-9):
    temp = pd.read_csv(pathName, sep=',').values
    movie_id = temp[:,0].astype(np.int32)
    temp_sim = temp[:,1:].astype(np.float32)
    sim = np.zeros(temp_sim.shape).astype(np.float32)
    starttime = time.time()
    print("Start loading sim matrix")
    for i in range(len(movie_id)):
        for j in range(len(movie_id)):
            sim[id_to_idx[movie_id[i]],id_to_idx[movie_id[j]]] = temp_sim[i,j]
    print("Sim matrix loaded ,time:{}".format(time.time()-starttime))    
    return sim+eps
        
trainingPathName = "./../dataset_partitioned/ratings_training.csv"
testPathName = "./../dataset_partitioned/ratings_test.csv"
headerName = ['user_id','item_id','rating','timestamp']

train_df = loadDF(trainingPathName,headerName)
test_df = loadDF(testPathName, headerName)

    
n_item = train_df.item_id.unique()
## create index between df index and raw item_id
index2_id = {}
id2_index = {}
for i in range(n_item.shape[0]):
    #print("{} {}".format(i,n_item[i]))
    index2_id[i] = n_item[i]
    id2_index[n_item[i]] = i

n_item = n_item.shape[0]
n_user = train_df.user_id.unique().shape[0]
#print("{} {}".format(n_user,n_item))


## fill up matrix with training data
train = np.zeros((n_user,n_item)).astype(np.float32)
for i in train_df.itertuples():
    #print( id2_index[i[2]])    
    train[i[1]-1, id2_index[i[2]]] = i[3]
print(train[:4,:4])

## create separate matrix to contain actual data (for testing)
test = np.zeros((n_user,n_item)).astype(np.float32)
for i in test_df.itertuples():
    #print( id2_index[i[2]])
    test[i[1]-1, id2_index[i[2]]] = i[3]

sparsity = float(len(train.nonzero()[0])) / n_user / n_item * 100
print("Train Sparsity: {:6.2f}%".format(sparsity))
sparsity = float(len(test.nonzero()[0])) / n_user / n_item * 100
print("Test Sparsity: {:6.2f}%".format(sparsity))


## adjusted rating with 0
## (in this case with 0 in the weighted sum calculation but mean centered without counting 0)
adjusted_rating_without_zero = train.copy()
nonzero_pos = [i.nonzero() for i in train]
user_mean_without_zero = [np.sum(train[i].take(nonzero_pos[i][0]))/len(nonzero_pos[i][0]) for i in range(len(nonzero_pos))]

alpha = 1
global_mean = np.sum(user_mean_without_zero)/len(user_mean_without_zero)
numEntry = np.array([len(i[0]) for i in nonzero_pos]).astype(np.float32)

user_mean_without_zero = alpha/(alpha+numEntry)*global_mean + numEntry/(alpha+numEntry)*user_mean_without_zero

for i in range(len(nonzero_pos)):
    for j in nonzero_pos[i]:
        adjusted_rating_without_zero[i,j] = adjusted_rating_without_zero[i,j] - user_mean_without_zero[i]
##


#cos_sim = cos_sim(train)
#adjusted_cos_sim = cos_sim(adjusted_rating_without_zero)
#correlation_sim = correlation_sim(train)

## newest_adjusted_cosine = adjusted cosine without 0
## similarity_cosine = cosine without 0
## similarity_correlation = correlation without 0
## change the name of the .csv below
#simName = "./../similarity_matrix/" + "newest_adjusted_cosine" + ".csv"
#without0_sim = load_kc_sim(simName,id2_index)

#print(item_sim[:4,:4])


#print(test[:4,:4])
k = [1,2,5,10,20,40,100]
## change sim with appropriate similarity
topk_mse(train,test,cos_sim,k)


#writePath = "top10-adjusted_cosine.txt"
#topk_to_file(writePath,item_sim,10)