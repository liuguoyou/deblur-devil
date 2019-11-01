# Author: Jochen Gast <jochen.gast@visinf.tu-darmstadt.de>

import torch
import torch.nn as nn

from contrib import weight_init
from models import factory


def conv(in_channels, out_channels, kernel_size,
         eps=1e-3,
         stride=1,
         padding=None,
         bias=False,
         nonlinear=True):
    if padding is None:
        padding = (kernel_size - 1) // 2
    if nonlinear:
        return nn.Sequential(
            nn.Conv2d(
                in_channels, out_channels,
                kernel_size=kernel_size, stride=stride,
                padding=padding, bias=bias),
            nn.BatchNorm2d(out_channels, eps=eps),
            nn.ReLU()
        )
    else:
        return nn.Sequential(
            nn.Conv2d(
                in_channels, out_channels,
                kernel_size=kernel_size, stride=stride,
                padding=padding, bias=bias),
            nn.BatchNorm2d(out_channels, eps=eps)
        )


def deconv(in_channels, out_channels, kernel_size=4,
           eps=1e-3,
           stride=2,
           padding=1,
           bias=False):
    return nn.Sequential(
        nn.ConvTranspose2d(
            in_channels, out_channels,
            kernel_size=kernel_size, stride=stride,
            padding=padding, bias=bias),
        nn.BatchNorm2d(out_channels, eps=eps))


class DBNImpl(nn.Module):

    def __init__(self, args, input_channels=15, output_channels=3, init_type='fan_max'):
        super().__init__()
        self.args = args
        ni = input_channels
        no = output_channels

        self.f0 = conv(ni, 64, kernel_size=5)

        self.d1 = conv(64, 64, kernel_size=3, stride=2)
        self.f1 = conv(64, 128, kernel_size=3)
        self.f2 = conv(128, 128, kernel_size=3)

        self.d2 = conv(128, 256, kernel_size=3, stride=2)
        self.f3 = conv(256, 256, kernel_size=3)
        self.f4 = conv(256, 256, kernel_size=3)
        self.f5 = conv(256, 256, kernel_size=3)

        self.d3 = conv(256, 512, kernel_size=3, stride=2)
        self.f6 = conv(512, 512, kernel_size=3)
        self.f7 = conv(512, 512, kernel_size=3)
        self.f8 = conv(512, 512, kernel_size=3)

        self.u1 = deconv(512, 256)
        self.s1 = nn.ReLU()
        self.f9 = conv(256, 256, kernel_size=3)
        self.f10 = conv(256, 256, kernel_size=3)
        self.f11 = conv(256, 256, kernel_size=3)

        self.u2 = deconv(256, 128)
        self.s2 = nn.ReLU()
        self.f12 = conv(128, 128, kernel_size=3)
        self.f13 = conv(128, 64, kernel_size=3)

        self.u3 = deconv(64, 64)
        self.s3 = nn.ReLU()
        self.f14 = conv(64, ni, kernel_size=3)
        self.f15 = conv(ni, no, kernel_size=3, nonlinear=False)

        if init_type == 'fan_max':
            weight_init.fanmax_(self.modules())
        elif init_type == 'fan_out':
            weight_init.msra_(self.modules(), mode='fan_out')
        elif init_type == 'fan_in':
            weight_init.msra_(self.modules(), mode='fan_in')
        else:
            raise ValueError('Unknown init!')

    def forward(self, inputs):
        x = torch.cat(inputs, dim=1)

        f0 = self.f0(x)

        d1 = self.d1(f0)
        f1 = self.f1(d1)
        f2 = self.f2(f1)

        d2 = self.d2(f2)
        f3 = self.f3(d2)
        f4 = self.f4(f3)
        f5 = self.f5(f4)

        d3 = self.d3(f5)
        f6 = self.f6(d3)
        f7 = self.f7(f6)
        f8 = self.f8(f7)

        u1 = self.u1(f8)
        s1 = self.s1(f5 + u1)
        f9 = self.f9(s1)
        f10 = self.f10(f9)
        f11 = self.f11(f10)

        u2 = self.u2(f11)
        s2 = self.s2(f2 + u2)
        f12 = self.f12(s2)
        f13 = self.f13(f12)

        u3 = self.u3(f13)
        s3 = self.s3(f0 + u3)
        f14 = self.f14(s3)
        f15 = self.f15(f14)

        model_dict = {'f15': f15}
        return model_dict


class DBN(nn.Module):
    def __init__(self, args, init_type='fan_max'):
        super().__init__()
        self.sequence_length = args.validation_dataset_sequence_length
        self.dbn_net = DBNImpl(args, input_channels=self.sequence_length * 3, output_channels=3, init_type=init_type)

    def forward(self, input_dict):
        inputs = [input_dict['input{}'.format(i + 1)] for i in range(self.sequence_length)]
        ref_idx = self.sequence_length // 2

        f15 = self.dbn_net(inputs)['f15']
        output = f15 + inputs[ref_idx]

        if not self.training:
            output.clamp_(0, 1)

        return {'output1': output}


factory.register("DBN", DBN)
