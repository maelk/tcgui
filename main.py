import subprocess, os, re, argparse
from flask import Flask, render_template, redirect, request, url_for


app = Flask(__name__)
pattern = None
dev_list = None

def parse_arguments():
    parser = argparse.ArgumentParser(description='TC web GUI')
    parser.add_argument('--ip', type=str, required=False,
                        help='The IP where the server is listening')
    parser.add_argument('--port', type=str, required=False,
                        help='The port where the server is listening')
    parser.add_argument('--dev', type=str, nargs='*', required=False,
                        help='The interfaces to restrict to')
    parser.add_argument('--dev-regex',type=str, required=False,
                        help='A regex to match interfaces')
    parser.add_argument('--debug',action='store_true',
                        help='Run Flask in debug mode')
    return parser.parse_args()


def add_rule(interface, delay, loss, duplicate, reorder, corrupt, rate):
    # remove old setup
    command = 'tc qdisc del dev %s root' % interface
    command = command.split(' ')
    proc = subprocess.Popen(command)
    proc.wait()

    # apply new setup
    command = 'tc qdisc add dev %s root netem' % interface
    if rate != '':
        command += ' rate %smbit' % rate
    if delay != '':
        command += ' delay %sms' % delay
    if loss != '':
        command += ' loss %s%%' % loss
    if duplicate != '':
        command += ' duplicate %s%%' % duplicate
    if reorder != '':
        if delay == '':
            return 'Reordering requires delay', 400
        command += ' reorder %s%%' % reorder
    if corrupt != '':
        command += ' corrupt %s%%' % corrupt
    command = command.split(' ')
    proc = subprocess.Popen(command)
    proc.wait()
    return redirect(url_for('main'))
    
def del_rule(interface):
    command = 'tc qdisc del dev %s root' % interface
    command = command.split(' ')
    proc = subprocess.Popen(command)
    proc.wait()
    
def get_params():
    params = {}
    params['delay'] = request.form['Delay']
    params['loss'] = request.form['Loss']
    params['duplicate'] = request.form['Duplicate']
    params['reorder'] = request.form['Reorder']
    params['corrupt'] = request.form['Corrupt']
    params['rate'] = request.form['Rate']
    return params
    
@app.route("/")
def main():
    rules = get_active_rules()
    return render_template('main.html', rules=rules)


@app.route('/modify-rule/<interface>', methods=['POST'])
def modify_rule(interface):
    return add_rule(interface, **get_params())

@app.route('/delete-rule/<interface>', methods=['POST'])
def remove_rule(interface):
    # remove old setup
    del_rule(interface)
    return redirect(url_for('main'))
    
@app.route('/modify-rules', methods=['POST'])
def modify_rules():
    params = get_params()
    if params['reorder'] != '' and params['delay'] == '' :
        return 'Reordering requires delay', 400
    for rule in get_active_rules():
        add_rule(rule['name'], **params)
    return redirect(url_for('main'))
    
@app.route('/delete-rules', methods=['POST'])
def remove_rules():
    # remove old setup
    for rule in get_active_rules():
        del_rule(rule['name'])
    return redirect(url_for('main'))

def get_active_rules():
    proc = subprocess.Popen(['tc', 'qdisc'], stdout=subprocess.PIPE)
    output = proc.communicate()[0].decode()
    lines = output.strip().split('\n')
    rules = []
    seen_dev = []
    for line in lines:
        arguments = line.split(' ')
        rule = parse_rule(arguments)
        if rule['name'] and rule['name'] not in seen_dev:
            rules.append(rule)
            seen_dev.append(rule['name'])
    return rules


def parse_rule(splitted_rule):
    rule = {'name':      None,
            'rate':      '',
            'delay':     '',
            'loss':      '',
            'duplicate': '',
            'reorder':   '',
            'corrupt':   ''}
    i = 0
    for argument in splitted_rule:
        if argument == 'dev':
            # Both regex pattern and dev name can be given
            # An interface could match the pattern and/or 
            # be in the interface list
            if pattern is None and dev_list is None:
                rule['name'] = splitted_rule[i+1]
            if pattern:
                if pattern.match(splitted_rule[i+1]) :
                    rule['name'] = splitted_rule[i+1]
            if dev_list:
                if splitted_rule[i+1] in dev_list:
                    rule['name'] = splitted_rule[i+1]
        elif argument == 'rate':
            rule['rate'] = splitted_rule[i + 1].split('Mbit')[0]
        elif argument == 'delay':
            rule['delay'] = splitted_rule[i + 1].split('ms')[0]
        elif argument == 'loss':
            rule['loss'] = splitted_rule[i + 1].split('%')[0]
        elif argument == 'duplicate':
            rule['duplicate'] = splitted_rule[i + 1].split('%')[0]
        elif argument == 'reorder':
            rule['reorder'] = splitted_rule[i + 1].split('%')[0]
        elif argument == 'corrupt':
            rule['corrupt'] = splitted_rule[i + 1].split('%')[0]
        i += 1
    return rule


if __name__ == "__main__":
    #if os.geteuid() != 0:
    #    exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")
    args = parse_arguments()
    if args.dev_regex:
        pattern = re.compile(args.dev_regex)
    if args.dev:
        dev_list = args.dev
    app_args={}
    if args.ip:
        app_args['host'] = args.ip
    if args.port:
        app_args['port'] = args.port
    if not args.debug:
        app_args['debug'] = False
    app.debug = True
    app.run(**app_args)
