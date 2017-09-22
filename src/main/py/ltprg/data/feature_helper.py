# import unittest
import sys
import numpy as np
from os.path import join
from mung.data import DataSet, Datum, Partition
from mung.feature import FeatureSet, DataFeatureMatrix
from feature import FeatureVisualEmbeddingType, FeatureCielabEmbeddingType

input_data_dir = sys.argv[1]
output_feature_dir = sys.argv[2]
partition_file = sys.argv[3]

# Necessary to allow unittest.main() to work
del sys.argv[3]
del sys.argv[2]
del sys.argv[1]

print input_data_dir
print output_feature_dir
print partition_file

np.random.seed(1)

def featurize_embeddings(input_data_dir, output_feature_dir, partition_file,
                         partition_fn, feature_name, paths, embedding_type, 
                         init_data="train"):
	assert embedding_type in ['fc-6', 'cielab']
	partition = Partition.load(partition_file)
	data_full = DataSet.load(input_data_dir)
	data_parts = data_full.partition(partition, partition_fn)
	if embedding_type == 'fc-6':
		feat = FeatureVisualEmbeddingType(feature_name, paths)
	elif embedding_type == 'cielab':
		feat = FeatureCielabEmbeddingType(feature_name, paths)
	feat_set = FeatureSet(feature_types=[feat])
	feat_set.init(data_parts[init_data])
	mat = DataFeatureMatrix(data_full, feat_set, init_features=False)
	mat.save(output_feature_dir)

class StimEmbeddings(object):
	def target_representation(self):
		# constructs target stimulus embedding
		'\nConstructing target stim representations\n'
		featurize_embeddings(
			input_data_dir, 
			output_feature_dir,
			partition_file,
			lambda d : d.get("gameid"),
			# "target_fc_embedding",
			"target_cielab_embedding",
			[["state.sTargetH", "state.sTargetS", "state.sTargetL"]],
			# "fc-6",
			 "cielab")
	
	def context_representation(self):
		# constructs concatenated embeddings for the 3 stimuli in a context
		'\nConstructing concatentated stim representations\n'
		featurize_embeddings(
			input_data_dir, 
			output_feature_dir,
			partition_file,
			lambda d : d.get("gameid"),
			# "context_fc_embedding",
			"context_cielab_embedding",
			[["state.lH_0", "state.lS_0", "state.lL_0"], 
			 ["state.lH_1", "state.lS_1", "state.lL_1"], 
			 ["state.lH_2", "state.lS_2", "state.lL_2"]],
			 # "fc-6",
			 "cielab")

if __name__=='__main__':
	em = StimEmbeddings()
	# em.target_representation()
	em.context_representation()