from sys import argv
from pymongo import Connection
from pymongo.code import Code

if len(argv) > 1 and argv[1].isalpha():
    stat = argv[1]
else:
    stat = "numerosity"

total_map = Code("""
    function () {
        stat = this.%s;
        emit('total', stat);
        emit('max', stat);
        emit('min', stat);
        emit('n ' + stat, 1)
        emit('count', 1);
    }
""" % stat)

# For some reason, `min` and `max` are not defined.
total_reduce = Code("""
    function (key, values) {
        var result = 0;
        switch (key) {
            case 'max':
                result = values[0];
                for (var i = 1; i < values.length; i++) {
                    if (values[i] > result) {
                        result = values[i];
                    }
                }
                break;
            case 'min':
                result = values[0];
                for (var i = 1; i < values.length; i++) {
                    if (values[i] < result) {
                        result = values[i];
                    }
                }
                break;
            case 'total':
            case 'count':
            default:
                for (var i = 0; i < values.length; i++) {
                    result += values[i];
                }
                break;
        }
        
        return result;
    }
""")

ttt = Connection().parang.tictactoe
for row in ttt.map_reduce(total_map, total_reduce).find():
    print "%(_id)s:\t%(value)s" % row
