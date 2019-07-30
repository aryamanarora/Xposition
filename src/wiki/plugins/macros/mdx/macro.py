import re

import markdown
from markdown.util import etree
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from wiki.plugins.macros import settings
from wiki.plugins.metadata import models
from django.utils.html import escape, mark_safe, format_html


#def handleMatch(self, m):
#    if m.group(2).strip():
#        base_url, end_url, html_class = self._getMeta()
#        label = m.group(2).strip()
#        url = self.config['build_url'](label, base_url, end_url, self.md)
#        a = markdown.util.etree.Element('a')
#        a.text = label
#        a.set('href', url)
#        if html_class:
#            a.set('class', html_class)
#    else:
#        a = ''
#    return a

# See:
# http://stackoverflow.com/questions/430759/regex-for-managing-escaped-characters-for-items-like-string-literals
re_sq_short = r'"([^"\\]*(?:\\.[^"\\]*)*)"'

# can't compile: markdown.inlinepatterns.Pattern expects a string
MACRO_RE = r"(?i)(\[(?P<macro>\w+)(?P<kwargs>(\s(\w+:)?(%s|[\w'`&!%%+/$-]+))*)\])" % re_sq_short
KWARG_RE = re.compile(
    r'\s*((?P<arg>\w+):)?(?P<value>(%s|[^\s:]+))' %
    re_sq_short,
    re.IGNORECASE)

# Positional macros were deprecated in markdown 3.0, so we need to kwargize
# the existing positional macros during the preprocessing step. This dict
# determines what the keywords will be for the macros with positional
# invocations.
POSITIONAL_MACROS = ["p", "pspecial", "ss", "exref", "ex", "gex"]

class MacroExtension(markdown.Extension):
    """ Macro plugin markdown extension for django-wiki. """

    def extendMarkdown(self, md):
        md.inlinePatterns.deregister('html')
        md.inlinePatterns.add('dw-macros', MacroPattern(MACRO_RE, md), '>link')


class MacroPattern(markdown.inlinepatterns.Pattern):

    """django-wiki macro preprocessor - parse text for various [some_macro] and
    [some_macro (kw:arg)*] references. """

    def handleMatch(self, m):
        macro = m.group('macro').strip()
        if macro not in settings.METHODS or not hasattr(self, macro):
            return m.group(2)

        kwargs = m.group('kwargs')
        if not kwargs:
            return getattr(self, macro)()
        kwargs_dict = {}
        for i, kwarg in enumerate(KWARG_RE.finditer(kwargs)):

            # Begin Xposition-specific hack: if there's no :, we have a positional macro
            arg = kwarg.group('arg')
            value = kwarg.group('value')
            if arg is None and macro in POSITIONAL_MACROS:
                arg = "arg" + str(i)
            elif arg is None:
                arg = value
                value = True
            if isinstance(value, str):
                # If value is enclosed with ': Remove and
                # remove escape sequences
                if value.startswith("'") and len(value) > 2:
                    value = value[1:-1]
                    value = value.replace("\\\\", "¤KEEPME¤")
                    value = value.replace("\\", "")
                    value = value.replace("¤KEEPME¤", "\\")
            kwargs_dict[str(arg)] = value
        return getattr(self, macro)(**kwargs_dict)

    def article_list(self, depth="2"):
        html = render_to_string(
            "wiki/plugins/macros/article_list.html",
            context={
                'article_children': self.markdown.article.get_children(
                    article__current_revision__deleted=False),
                'depth': int(depth) + 1,
            })
        return self.markdown.htmlStash.store(html)
    article_list.meta = dict(
        short_description=_('Article list'),
        help_text=_('Insert a list of articles in this level.'),
        example_code='[article_list depth:2]',
        args={'depth': _('Maximum depth to show levels for.')}
    )

    def toc(self):
        return "[TOC]"
    toc.meta = dict(
        short_description=_('Table of contents'),
        help_text=_('Insert a table of contents matching the headings.'),
        example_code='[TOC]',
        args={}
    )

    def wikilink(self):
        return ""
    wikilink.meta = dict(
        short_description=_('WikiLinks'),
        help_text=_(
            'Insert a link to another wiki page with a short notation.'),
        example_code='[[WikiLink]]',
        args={})


    def p(self, **kwargs):
        args = argize_kwargs(kwargs)
        cl = None
        prep = args[0]
        short = prep.split('/')[-1]
        p = models.Adposition.normalize_adp(cls=models.Adposition,
                                            adp=short,
                                            language_name=prep.split('/')[-2])
        if p:
            prep = prep.replace(short, p)
        if len(args) >= 3:
            cl = args[2]
        if len(args) > 1 and not '-' == args[1]:
            construal = args[1]
            if '`' in construal:
                return link(short, '/' + prep + '/' + construal, cl if cl else 'usage')
            elif '--' in construal or "'" in construal or '?' in construal:
                return link(short.replace('--','&#x219d;'), '/' + prep + '/' + construal, cl if cl else 'usage')
            else:
                return link(short, '/' + prep + '/' + construal + '--' + construal, cl if cl else 'usage')
        return link(short, '/' + prep, cl if cl else 'adposition')
    # meta data
    p.meta = dict(
        short_description=_('Link to Adposition, Usage'),
        help_text=_('Create a link to a preposition or preposition-construal pair'),
        example_code='[p en/in] or [p en/in Locus--Locus]',
        args={'prep': _('Name of adposition'), 'construal': _('Name of construal'), 'class': _('optional class')}
    )

    def pspecial(self, **kwargs):
        args = argize_kwargs(kwargs)
        cl = None
        text = args[0]
        prep = args[1]
        p = models.Adposition.normalize_adp(cls=models.Adposition,
                                            adp=prep.split('/')[-1],
                                            language_name=prep.split('/')[-2])
        if p:
            prep = prep.replace(prep.split('/')[-1], p)
        if len(args) >= 4:
            cl = args[3]
        if len(args) > 2 and not '-' == args[2]:
            construal = args[2]
            if '`' in construal:
                return link(text, '/' + prep + '/' + construal, cl if cl else 'usage')
            elif '--' in construal or "'" in construal or '?' in construal:
                return link(text.replace('--', '&#x219d;'), '/' + prep + '/' + construal, cl if cl else 'usage')
            else:
                return link(text, '/' + prep + '/' + construal + '--' + construal, cl if cl else 'usage')
        return link(text, '/' + prep, cl if cl else 'adposition')
    # meta data
    pspecial.meta = dict(
        short_description=_('Link to Adposition, Usage'),
        help_text=_('Create a link to a preposition or preposition-construal pair with special (nonstandard) spelling or noncanonical capitalization'),
        example_code='[pspecial In en/in] or [pspecial In en/in Locus--Locus]',
        args={'prep': _('Name of adposition'), 'special': _('Text to display'), 'construal': _('Name of construal'), 'class': _('optional class')}
    )


    def ss(self, **kwargs):
        args = argize_kwargs(kwargs)
        cl = None
        if len(args) >= 2:
            cl = args[1]
        if '--' in args[0]:
            display = args[0].replace('--','&#x219d;')
            cls = cl or 'construal'
            if args[0]==self.markdown.article.current_revision.title:
                span = etree.Element("span")
                span.set("class", cls)
                span.set("this-construal", "this-construal")
                span.text = display
                return span
            return link(display, '/' + args[0], cl if cl else 'construal')
        else:
            display = args[0].replace('`',r'\`')
            cls = cl or 'supersense'
            if args[0] in ['??','`d','`i','`c','`$']:
                cls = cl or 'misc-label'
            if args[0] == self.markdown.article.current_revision.title:
                span = etree.Element("span")
                span.set("class", cls)
                span.set("this-construal", "this-construal")
                span.text = display
                return span
            return link(display, '/' + args[0].replace('`','%60'), cls)
    # meta data
    ss.meta = dict(
        short_description=_('Link to Supersense or Construal'),
        help_text=_('Create a link to a supersense or construal'),
        example_code='[ss Locus] or [ss Locus--Locus]',
        args={'name': _('Name of supersense/construal label'), 'class': _('optional class')}
    )

    def exref(self, **kwargs):
        args = argize_kwargs(kwargs)
        id = args[0]
        page = args[1]
        my_title = self.markdown.article.current_revision.title
        ref_title = page
        ref_slug = page
        # try to find article
        x = Article.objects.filter(current_revision__title=ref_title)
        # check for article with matching title
        if x:
            ref_slug = str(x[0].urlpath_set.all()[0])
            if ref_slug[0]=='/':
                ref_slug = ref_slug[1:]
            if ref_slug[-1]=='/':
                ref_slug = ref_slug[:-1]
        display = f'{ref_title}#{id}' if not ref_title==my_title else f'#{id}'
        return link(display, '/' + ref_slug + '/#' + id, 'exref')

    # meta data
    exref.meta = dict(
        short_description=_('Link to Example'),
        help_text=_('Create a link to an example sentence'),
        example_code='[exref 001 Locus]',
        args={'id': _('id of example'), 'page': _('title of page example is on')}
    )

    def ex(self, **kwargs):
        args = argize_kwargs(kwargs)
        id = args[0]
        sent = args[1]
        label = args[2] if len(args) > 2 else None

        span = etree.Element("span")
        span.set("id", id)
        sent_span = etree.SubElement(span, "span")
        sent_span.text = sent + " "
        if label:
            exlabel_span = etree.SubElement(span, "span")
            exlabel_span.set("class", "exlabel")
            exlabel_span.text = label
        else:
            exlabel_a = etree.SubElement(span, "a")
            exlabel_a.set("class", "exlabel")
            exlabel_a.set("id", "#" + id)
            exlabel_a.text = id

        return span
    # meta data
    ex.meta = dict(
        short_description=_('Create an Example'),
        help_text=_('Create an example sentence with a linkable id'),
        example_code='[ex 001 "The cat [p en/under Locus] the table."]',
        args={'id': _('id of example'), 'sent': _('full sentence in double quotes'), 'label': _('string to display after ex. (if not id)')}
    )

    GLOSS_RE = re.compile('^\{(?P<tok_gloss>[^}]*?)\}')
    def gex(self, **kwargs):
        args = argize_kwargs(kwargs)
        id = args[0]
        sent = args[1]
        sent_gloss = args[2] if len(args) > 2 else ''
        columns = []
        while len(sent)>0:
            gloss = self.GLOSS_RE.match(sent)
            if gloss:
                word_gloss = gloss.group('tok_gloss')
                sent = sent[len(gloss.group()):]
                if '||' in word_gloss:
                    xs = word_gloss.split('||')
                else:
                    xs = word_gloss.split()
                xs = [escape(x) for x in xs]
                column = '<div class="gll">'+'<br />'.join(xs)+'</div>'
            else:
                end = sent.index('{') if '{' in sent else len(sent)
                word_gloss = sent[:end]
                sent = sent[len(word_gloss):]
                if word_gloss.strip():
                    column = '<div class="gll">' + word_gloss.strip() + '</div>'
                else:
                    column = ''
            columns.append(column)
        interlinear = ''.join(columns)
        interlinear = format_html(f'''<span id="{id}" class="example">
                    <div class="interlinear example">
                    <p class="gloss">
                        {interlinear}
                    </p>
                    <p class="translation">{{}}&nbsp;<a href="#{{}}" class="exlabel">{{}}</a></p>
                    </div></span>
                    ''', sent_gloss, id, id)
        return interlinear
    # meta data
    gex.meta = dict(
        short_description=_('Create a Glossed Example'),
        help_text=_('Create an example sentence word and sentence translation displayed on separate lines.'),
        example_code='[gex 001 '
                     '"{L\' the}{éléphant elephant} {gris gray} est<br> {[p fr/dans Locus]||[p en/in Locus]} {la voiture||the car}." '
                     '"The gray elephant is in the car."]',
        args={'id': _('id of example'),
              'sent': _('full sentence in double quotes with glossed tokens as {token||gloss}'),
              'sent_gloss': _('glossed translation of sentence'),
              'label': _('string to display after ex. (if not id)')}
    )


def link(t, l, clazz):
    a = etree.Element("a")
    a.set("href", l)
    a.set("class", clazz)
    a.text = t
    return a

def makeExtension(*args, **kwargs):
    """Return an instance of the extension."""
    return MacroExtension(*args, **kwargs)

def argize_kwargs(kwargs):
    args = []
    # arg0, arg1, ..., arg10, etc.
    for arg in sorted(kwargs.keys(), key=lambda x:int(x[3:])):
        args.append(kwargs[arg])
    return args

