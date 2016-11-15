from utils import identity
import utils
import pprint
from abc import ABCMeta, abstractmethod
from inspect import isclass


###############################
# Helpers
###############################

NO_VALUE = object()

class Ref(object):
    """docstring for Ref."""
    def __init__(self, name, value=NO_VALUE):
        super(Ref, self).__init__()
        self.name = name
        self.value = None if value is NO_VALUE else value
        self.assigned = value is not NO_VALUE

    def __call__(self, *optional):
        if not self.assigned:
            raise Exception("Trying to read Ref('{0}') before assignment".format(self.name))

        return self.value

    def set(self, x):
        self.value = x

        if not self.assigned:
            self.assigned = True

        return x

class Record(dict):
    """docstring for DictObject."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __setitem__(self, key, item):
        self.__dict__[key] = item

    def __getitem__(self, key):
        return self.__dict__[key]

    def __repr__(self):
        return repr(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __delitem__(self, key):
        del self.__dict__[key]

    def clear(self):
        return self.__dict__.clear()

    def copy(self):
        return self.__dict__.copy()

    def has_key(self, k):
        return self.__dict__.has_key(k)

    def pop(self, k, d=None):
        return self.__dict__.pop(k, d)

    def update(self, *args, **kwargs):
        return self.__dict__.update(*args, **kwargs)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def pop(self, *args):
        return self.__dict__.pop(*args)

    def __cmp__(self, dict):
        return cmp(self.__dict__, dict)

    def __contains__(self, item):
        return item in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)

    def __unicode__(self):
        return unicode(repr(self.__dict__))

###############################
# DSL Elements
###############################

class Node(object):
    """docstring for Node."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def __compile__(self, refs):
        pass

class Function(Node):
    """docstring for Function."""
    def __init__(self, f):
        super(Function, self).__init__()
        self._f= f
        self._refs = {}

    def __iter__(self):
        yield self

    def __compile__(self, refs):
        refs = dict(refs, **self._refs)
        return self._f, refs

    def __str__(self):
        return "Fun({0})".format(self._f)


Identity = Function(identity)


class Tree(Node):
    """docstring for Tree."""

    def __init__(self, branches):
        self.branches = list(branches)

    def __compile__(self, refs):
        fs = []

        for node in self.branches:
            node_fs, refs = node.__compile__(refs)

            if type(node_fs) is list:
                fs += node_fs
            else:
                fs.append(node_fs)

        return fs, refs

    def __str__(self):
        return pprint.pformat(self.branches)


class Sequence(Node):
    """docstring for Sequence."""
    def __init__(self, left, right):
        super(Sequence, self).__init__()
        self.left = left
        self.right = right

    def __compile__(self, refs):
        f_left, refs = self.left.__compile__(refs)

        f_left = to_fn(f_left)

        f_right, refs = self.right.__compile__(refs)

        f_right = compose(f_right, f_left)

        return f_right, refs

    def __str__(self):
        return "Seq({0}, {1})".format(self.left, self.right)

class Dict(Node):
    """docstring for Dict."""
    def __init__(self, dict_code):
        super(Dict, self).__init__()
        self.nodes_dict = { key: parse(code) for key, code in dict_code.iteritems() }

    @classmethod
    def __parse__(cls, dict_code):
        return Dict(dict_code)

    def __compile__(self, refs):
        funs_dict = {}
        out_refs = refs.copy()

        for key, node in self.nodes_dict.iteritems():
            fs, next_refs = node.__compile__(refs)
            f = to_fn(fs)

            out_refs.update(next_refs)
            funs_dict[key] = f

        def function(x):
            return Record(**{key: f(x) for key, f in funs_dict.iteritems() })

        return function, out_refs



class With(Node):
    """docstring for Dict."""

    GLOBAL_SCOPE = None

    def __init__(self, scope_code, body_code):
        super(With, self).__init__()
        self.scope = parse(scope_code, else_constant=True)
        self.body = parse(body_code)

    def __compile__(self, refs):
        scope_f, refs = self.scope.__compile__(refs)
        body_fs, refs = self.body.__compile__(refs)

        def function(x):
            with scope_f(x) as scope:
                with self.set_scope(scope):
                    return body_fs(x)

        return function, refs

    def set_scope(self, new_scope):
        self.new_scope = new_scope
        self.old_scope = With.GLOBAL_SCOPE

        return self

    def __enter__(self):
        With.GLOBAL_SCOPE = self.new_scope

    def __exit__(self, *args):
        With.GLOBAL_SCOPE = self.old_scope

    def __str__(self):
        return "\{ {0}: {1}\}".format(pprint.pformat(self.scope), pprint.pformat(self.body))

class Read(Node):
    """docstring for Read."""
    def __init__(self, name):
        super(Read, self).__init__()
        self.name = name

    def __compile__(self, refs):
        ref = refs[self.name]
        f = ref #ref is callable with an argument
        return f, refs


class Write(Node):
    """docstring for Read."""
    def __init__(self, ref):
        super(Write, self).__init__()
        self.ref = ref

    def __compile__(self, refs):

        if type(self.ref) is str:
            name = self.ref

            if name in refs:
                self.ref = refs[name]
            else:
                refs = refs.copy()
                refs[name] = self.ref = Ref(self.ref)

        elif self.ref.name not in refs:
            refs = refs.copy()
            refs[self.ref.name] = self.ref

        return self.ref.set, refs


class Input(Node):
    """docstring for Input."""
    def __init__(self, value):
        super(Input, self).__init__()
        self.value = value

    def __compile__(self, refs):
        f = lambda x: self.value
        return f, refs


class Apply(Node):
    """docstring for Read."""
    def __init__(self):
        super(Write, self).__init__()

def compose(fs, g):
    if type(fs) is list:
        return [ utils.compose2(f, g) for f in fs ]
    else:
        return utils.compose2(fs, g)


def to_fn(fs):
    if type(fs) is list:
        return lambda x: [ f(x) for f in fs ]
    else:
        return fs

#######################
### FUNCTIONS
#######################

def Compile(code, refs):
    ast = parse(code)
    fs, refs = ast.__compile__(refs)

    fs = to_fn(fs)

    return fs, refs


def is_iter_instance(x):
    return hasattr(x, '__iter__') and not isclass(x)

def parse(code, else_constant=False):
    #if type(code) is tuple:
    if isinstance(code, Node):
        return code
    elif hasattr(code, '__call__') or isclass(code):
        return Function(code)
    elif type(code) is str:
        return Read(code)
    elif type(code) is set:
        return parse_set(code)
    elif type(code) is tuple:
        return parse_tuple(code)
    elif type(code) is dict:
        return Dict.__parse__(code)
    elif is_iter_instance(code): #leave last
        return parse_iterable(code) #its iterable
    elif else_constant:
        return Input(code)
    else:
        raise Exception("Parse Error: Element not part of the DSL. Got:\n{0} of type {1}".format(code, type(code)))

def parse_set(code):
    if len(code) == 0:
        return Identity

    for ref in code:
        if not isinstance(ref, (str, Ref)):
            raise Exception("Parse Error: Sets can only contain strings or Refs, get {0}".format(code))

    writes = tuple([ Write(ref) for ref in code ])
    return parse(writes)

def build_sequence(right, *prevs):
    left = prevs[0] if len(prevs) == 1 else build_sequence(*prevs)
    return Sequence(left, right)

def parse_tuple(tuple_code):
    nodes = [ parse(code) for code in tuple_code ]

    if len(nodes) == 0:
        return Identity

    if len(nodes) == 1:
        return nodes[0]

    nodes.reverse()

    return build_sequence(*nodes)


def parse_iterable(iterable_code):
    nodes = [ parse(code) for code in iterable_code ]

    if len(nodes) == 1:
        return nodes[0]

    return Tree(nodes)

def parse_dictionary(dict_code):

    if len(dict_code) != 1:
        raise Exception("Parse Error: dict object has to have exactly 1 element. Got {0}".format(dict_code))

    scope_code, body_code = list(dict_code.items())[0]
    body = parse(body_code)

    if not hasattr(scope_code, '__call__'):
        scope = Input(scope_code)
    else:
        scope = parse(scope_code)

    return With(scope, body)
