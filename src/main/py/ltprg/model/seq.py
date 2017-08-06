import sys
import time
import torch.nn as nn
import numpy as np
import torch
import abc
from torch.optim import Adam

class SamplingMode:
    FORWARD = 0
    BEAM = 1

class VariableLengthNLLLoss(nn.Module):
    def __init__(self):
    """
        Constructs NLLLoss for variable length sequences.

        Borrowed from
        https://github.com/ruotianluo/neuraltalk2.pytorch/blob/master/misc/utils.py
    """
        super(VariableLengthNLLLoss, self).__init__()

    def _to_contiguous(self, tensor):
        if tensor.is_contiguous():
            return tensor
        else:
            return tensor.contiguous()

    def forward(self, input, target, mask):
        # truncate to the same size
        #target = target[:, :input.size(1)]
        #mask =  mask[:, :input.size(1)]
        input = self._to_contiguous(input).view(-1, input.size(2))
        target = self._to_contiguous(target).view(-1, 1)
        mask = self._to_contiguous(mask).view(-1, 1)
        output = - input.gather(1, target)
        output = output *  mask
        output = torch.sum(output) / torch.sum(mask)

        return output


class SequenceModel(object, nn.Module):
    __metaclass__ = abc.ABCMeta

    def __init__(self, hidden_size):
        super(SequenceModel, self).__init__()
        self._hidden_size = hidden_size

    @abc.abstractmethod
    def _init_hidden(self, input=None):
        """ Initializes hidden state, possibly given some input """"

    @abc.abstractmethod
    def _forward_from_hidden(self, hidden, seq_part, seq_length, input=None):
        """ Runs the model forward from a given hidden state """

    def get_hidden_size(self):
        return self._hidden_size

    def forward(self, seq_part=None, seq_length=None, input=None):
        if seq_part is None:
            n = 1
            if input is not None:
                n = input.size(0)
            seq_part = torch.Tensor([Symbol.index(Symbol.SEQ_START)]) \
                .repeat(n).long().view(1, n)
            seq_length = torch.ones(1)

        hidden = self._init_hidden(input=input)
        return self._forward_from_hidden(hidden, seq_part, seq_length, input=input)

    def learn(self, data, data_input, data_seq, iterations, batch_size, eval_data=None, lr=0.001):
        # 'train' enables dropout
        self.train()
        total_loss = 0
        start_time = time.time()
        optimizer = Adam(self.parameters(), lr=lr)
        loss_criterion = VariableLengthNLLLoss()

        for i in range(iterations):
            batch = data.get_random_batch(batch_size)
            input = Variable(batch[data_input])
            seq, length, mask = batch[data_seq]
            length = length - 1

            seq_in = Variable(seq[:seq.size(0)-1]).long() # Input remove final token
            target_out = Variable(seq[1:seq.size(0)]).long() # Output (remove start token)

            model_out, hidden = self(seq_part=seq_in, seq_length=length, input=input)
            loss = loss_criterion(model_out, target_out[:model_out.size(0)], Variable(mask[:,1:(model_out.size(0)+1)]))

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.data

            if i % LOG_INTERVAL == 0 and i > 0:
                cur_loss = total_loss[0] / LOG_INTERVAL
                elapsed = time.time() - start_time
                eval_loss = 0.0
                if eval_data is not None:
                    eval_loss = self.evaluate(eval_data, data_input, data_seq, loss_criterion)
                print('| {:5d}/{:d} batches |  ms/batch {:5.2f} | '
                        'train loss {:5.7f} | eval loss {:5.7f}'.format(
                    i, iterations, elapsed * 1000 / LOG_INTERVAL, cur_loss, eval_loss))
                total_loss = 0
                start_time = time.time()

        # 'eval' disables dropout
        self.eval()

    def evaluate(self, data, data_input, data_seq, loss_criterion=None):
        # Turn on evaluation mode which disables dropout.
        self.eval()

        if loss_criterion is None:
            loss_criterion = VariableLengthNLLLoss()

        batch = data.get_batch(0, data.get_size())
        input = Variable(batch[data_input])
        seq, length, mask = batch[data_seq]
        length = length - 1

        seq_in = Variable(utterance[:seq.size(0)-1]).long() # Input remove final token
        target_out = Variable(utterance[1:seq.size(0)]).long() # Output (remove start token)

        model_out, hidden = self(seq_part=seq_in, seq_length=length, input=input)
        loss = loss_criterion(model_out, target_out[:model_out.size(0)], Variable(mask[:,1:(model_out.size(0)+1)]))

        self.train()
        return loss.data[0]

    # NOTE: Assumes seq_part does not contain end tokens
    def sample(self, n_per_input=1, seq_part=None, max_length=15, input=None):
        n = 1
        input_count = 1
        if input is not None:
            input_count = input.size(0)
            n = input.size(0) * n_per_input
            input = input.repeat(1, n_per_input).view(n, input.size(0))

        if seq_part is not None:
            input_count = seq_part.size(1)
            n = seq_part.size(1) * n_per_input
            seq_part = seq_part.repeat(n_per_input, 1).view(seq_part.size(0), n)
        else:
            seq_part = torch.Tensor([Symbol.index(Symbol.SEQ_START)]) \
                .repeat(n).long().view(1,n)

        end_idx = Symbol.index(Symbol.SEQ_END)
        ended = np.zeros(shape=(n))
        ended_count = 0
        unit_length = torch.ones(n).long()
        seq_length = unit_length*seq_part.size(0)
        sample = copy.deepcopy(seq_part)
        output, hidden = self(seq_part=Variable(seq_part), seq_length=seq_length, input=Variable(input))
        for i in range(seq_part.size(0), max_length):
            output_dist = output[output.size(0)-1].exp()
            next_token = torch.multinomial(output_dist).data
            sample = torch.cat((sample, next_token.transpose(1,0)), dim=0)
            output, hidden = self._forward_from_hidden(hidden,
                                                       Variable(next_token.view(1, next_token.size(0))),
                                                       unit_length,
                                                       input=input)

            for j in range(next_token.size(0)):
                seq_length[j] += 1 - ended[j]
                if next_token[j][0] == end_idx:
                    ended[j] = 1
                    ended_count += 1

            if ended_count == n:
                break

        # Return a list... like beam search...
        ret_samples = []
        for i in range(input_count):
            # FIXME Add score at some point
            ret_samples.append((sample[i*n_per_input:(i+1)*n_per_input], seq_length[i*n_per_input:(i+1)*n_per_input], 0.0))
        return ret_samples

    # NOTE: Input is a batch of inputs
    def beam_search(self, beam_size=5, max_length=15, seq_part=None, input=None):
        beams = []
        if seq_part is not None:
            seq_part = seq_part.transpose(1,0)

        for i in range(input.size(0)):
            seq_part_i = None
            if seq_part is not None:
                seq_part_i = seq_part[i].transpose(1,0)
            beams.append(self._beam_search_single(beam_size, max_length, seq_part=seq_part_i, input=input[i], heuristic=heuristic))
        return beams

    def _beam_search_single(self, beam_size, max_length, seq_part=None, input=None, heuristic):
        if seq_part is None:
            seq_part = torch.Tensor([Symbol.index(Symbol.SEQ_START)]).long().view(1,1)
        else:
            seq_part = seq_part.view(seq_part.size(0), 1)

        if input is not None:
            input = input.view(1, input.size(0))

        end_idx = Symbol.index(Symbol.SEQ_END)
        ended = np.zeros(shape=(beam_size))
        unit_length = torch.ones(beam_size).long()
        seq_length = unit_length*seq_part.size(0)

        output, hidden = self(seq_part=Variable(seq_part), seq_length=seq_length, input=Variable(input))
        hidden = hidden.repeat(1,1, beam_size).view(1, beam_size, hidden.size(2))

        beam = seq_part.repeat(1,beam_size).view(1,beam_size)
        scores = torch.zeros(1) #beam_size)

        for i in range(seq_part.size(0), max_length):
            output_dist = output[output.size(0)-1]
            vocab_size = output_dist.size(1)
            next_scores = scores.repeat(vocab_size).view(output_dist.size()) + output_dist.data

            # FIXME: If heuristic is not none, add heuristic function values here

            top_indices = next_scores.view(next_scores.size(0)*next_scores.size(1)).topk(beam_size)[1]
            top_seqs = top_indices / vocab_size
            top_exts = top_indices % vocab_size

            next_beam = torch.zeros(beam.size(0) + 1, beam_size).long()
            next_hidden = torch.zeros(1, beam_size, hidden.size(2))
            next_seq_length = unit_length*seq_part.size(0)
            next_ended = np.zeros(shape=(beam_size))
            scores = torch.zeros(beam_size)
            for j in range(beam_size):
                scores[j] = next_scores[top_seqs[j], top_exts[j]]
                next_beam[0:i,j] = beam[:,top_seqs[j]]
                next_beam[i,j] = top_exts[j]
                next_hidden[0,j] = hidden[0,top_seqs[j]]

                next_seq_length[j] = seq_length[top_seqs[j]] + (1 - ended[top_seqs[j]])
                next_ended[j] = ended[top_seqs[j]]
                if top_exts[j] == end_idx and next_ended[j] != 1:
                    next_ended[j] = 1
            beam = next_beam
            hidden = next_hidden
            seq_length = next_seq_length
            ended = next_ended

            if sum(ended) == beam_size:
                break

            output, hidden = self._forward_from_hidden(hidden,
                                                       Variable(beam[i].view(1,beam[i].size(0))),
                                                       unit_length,
                                                       input=input)

        return beam, seq_length, scores


class SequenceModelInputToHidden(SequenceModel):
    def __init__(self, seq_size, input_size, embedding_size, rnn_size,
                 rnn_layers, dropout=0.5):
        super(SequenceModelInputToHidden, self).__init__(rnn_size)

        self._rnn_layers = rnn_layers
        self._encoder = nn.Linear(input_size, rnn_size)
        self._encoder_nl = nn.Tanh()
        self._drop = nn.Dropout(dropout)
        self._emb = nn.Embedding(seq_size, embedding_size)
        self._rnn = getattr(nn, 'GRU')(embedding_size, rnn_size, rnn_layers, dropout=dropout)
        self._decoder = nn.Linear(rnn_size, utterance_size)
        self._softmax = nn.LogSoftmax()

        # Possibly add this back in later.  And add lstm support (need cell
        # state )
        #if rnn_type in ['LSTM', 'GRU']:
        #    self._rnn = getattr(nn, rnn_type)(embedding_size, rnn_size,
        #                                      rnn_layers, dropout=dropout)
        #else:
        #    try:
        #        nonlinearity = {'RNN_TANH': 'tanh', 'RNN_RELU': 'relu'}[rnn_type]
        #    except KeyError:
        #        raise ValueError( """An invalid option for `--model` was supplied,
        #                         options are ['LSTM', 'GRU', 'RNN_TANH' or 'RNN_RELU']""")
        #    self_.rnn = nn.RNN(embedding_size, rnn_size, rnn_layers,
        #                       nonlinearity=nonlinearity, dropout=dropout)


    def _init_hidden(self, input=None):
        hidden = self._encoder_nl(self._encoder(world))
        hidden = hidden.view(self._rnn_layers, hidden.size()[0], hidden.size()[1])
        return hidden

    def _forward_from_hidden(self, hidden, seq_part, seq_length, input=None):
        emb_pad = self._drop(self._emb(utterance_part))
        emb = nn.utils.rnn.pack_padded_sequence(emb_pad, utterance_length, batch_first=False)

        output, hidden = self._rnn(emb, hidden)

        output, _ = nn.utils.rnn.pad_packed_sequence(output, batch_first=False)
        rnn_out_size = output.size()

        output = self._softmax(self._decoder(output.view(-1, rnn_out_size[2])))
        output = output.view(rnn_out_size[0], rnn_out_size[1], output.size(1))

        return output, hidden

    def init_weights(self):
        initrange = 0.1
        self._emb.weight.data.uniform_(-initrange, initrange)
        self._encoder.bias.data.fill_(0)
        self._encoder.weight.data.uniform_(-initrange, initrange)
        self._decoder.bias.data.fill_(0)
        self._decoder.weight.data.uniform_(-initrange, initrange)