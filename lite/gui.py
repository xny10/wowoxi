"""Small Tkinter UI; crawler and CSV writer never run on the UI thread."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .bot import Bot
from .storage import Store


class App:
    def __init__(self, root, data_dir):
        self.root=root; self.store=Store(data_dir/'lite.sqlite3')
        self.events=queue.Queue(); self.bot=Bot(self.store,self.events)
        self.selected=None; self.offset=0; self.history_offset=0
        self.export_thread=None; self.closing=False
        root.title('AdRadar Lite Turbo · Grab + CSV');root.geometry('1020x760');root.minsize(820,620)
        style=ttk.Style(root)
        if 'clam' in style.theme_names():style.theme_use('clam')
        style.configure('TButton',padding=7);style.configure('TLabel',font=('Segoe UI',10))
        style.configure('Title.TLabel',font=('Segoe UI',22,'bold'))
        style.configure('Treeview',rowheight=27)
        frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='AdRadar Lite Turbo',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Grab URL tujuan + link iklan. Turbo incremental DOM aktif.').pack(anchor='w',pady=(0,14))
        form=ttk.LabelFrame(frame,text='Sesi baru',padding=12);form.pack(fill='x')
        self.name=tk.StringVar();self.url=tk.StringVar()
        for label,var in [('Nama sesi',self.name),('URL Ads Library',self.url)]:
            row=ttk.Frame(form);row.pack(fill='x',pady=3)
            ttk.Label(row,text=label,width=17).pack(side='left')
            ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        opts=ttk.Frame(form);opts.pack(fill='x',pady=8)
        self.headless=tk.BooleanVar(value=True);self.block=tk.BooleanVar(value=True);self.summary=tk.BooleanVar(value=False)
        for title,var in [('Headless',self.headless),('Blokir gambar/video/font',self.block),('Buka detail ringkasan (lebih berat)',self.summary)]:
            ttk.Checkbutton(opts,text=title,variable=var).pack(side='left',padx=(0,18))
        timing=ttk.Frame(form);timing.pack(fill='x')
        self.scroll=tk.StringVar(value='2');self.refresh=tk.StringVar(value='60')
        ttk.Label(timing,text='Jeda scroll (detik)').pack(side='left')
        ttk.Spinbox(timing,from_=0.5,to=30,increment=0.5,textvariable=self.scroll,width=6).pack(side='left',padx=8)
        ttk.Label(timing,text='Tunggu saat macet (detik)').pack(side='left')
        ttk.Spinbox(timing,from_=10,to=3600,increment=10,textvariable=self.refresh,width=7).pack(side='left',padx=8)
        self.start_btn=ttk.Button(timing,text='Start sesi baru',command=self.start);self.start_btn.pack(side='right')
        bar=ttk.Frame(frame);bar.pack(fill='x',pady=12)
        self.stop_btn=ttk.Button(bar,text='Stop proses aktif',command=self.stop);self.stop_btn.pack(side='left')
        self.resume_btn=ttk.Button(bar,text='Lanjutkan sesi terpilih',command=self.resume);self.resume_btn.pack(side='left',padx=8)
        self.export_btn=ttk.Button(bar,text='Export CSV',command=self.export);self.export_btn.pack(side='left')
        self.count=tk.StringVar(value='Pilih sesi dari History.');ttk.Label(bar,textvariable=self.count).pack(side='right')
        self.status=tk.StringVar(value='Siap.');ttk.Label(frame,textvariable=self.status,wraplength=960).pack(anchor='w',pady=(0,10))
        book=ttk.Notebook(frame);book.pack(fill='both',expand=True)
        history=ttk.Frame(book,padding=8);results=ttk.Frame(book,padding=8)
        book.add(history,text='History');book.add(results,text='Lihat hasil')
        self.hist=self.table(history,('name','count','status','created'),('Nama sesi','Jumlah','Status','Dibuat'),(370,90,100,210))
        self.hist.bind('<<TreeviewSelect>>',self.pick)
        hb=ttk.Frame(history);hb.pack(fill='x',pady=8)
        ttk.Button(hb,text='Refresh history',command=self.load_history).pack(side='left')
        ttk.Button(hb,text='←',command=lambda:self.history_page(-100)).pack(side='left',padx=6)
        ttk.Button(hb,text='→',command=lambda:self.history_page(100)).pack(side='left')
        ttk.Button(hb,text='Hapus sesi terpilih',command=self.delete).pack(side='right')
        self.rows=self.table(results,('url','link'),('Destination URL','Link Iklan Aktif'),(530,380))
        rb=ttk.Frame(results);rb.pack(fill='x',pady=8)
        ttk.Button(rb,text='Muat hasil',command=self.load_rows).pack(side='left')
        ttk.Button(rb,text='←',command=lambda:self.page(-100)).pack(side='left',padx=6)
        ttk.Button(rb,text='→',command=lambda:self.page(100)).pack(side='left')
        self.page_text=tk.StringVar(value='Maksimal 100 baris per halaman.');ttk.Label(rb,textvariable=self.page_text).pack(side='left',padx=12)
        ttk.Label(frame,text='Hasil disimpan otomatis. Tutup aplikasi atau klik Stop untuk mengakhiri proses.',wraplength=950).pack(anchor='w',pady=(10,0))
        self.load_history();root.protocol('WM_DELETE_WINDOW',self.close);root.after(300,self.poll)

    @staticmethod
    def table(parent,columns,labels,widths):
        box=ttk.Frame(parent);box.pack(fill='both',expand=True)
        tree=ttk.Treeview(box,columns=columns,show='headings',selectmode='browse')
        y=ttk.Scrollbar(box,orient='vertical',command=tree.yview)
        x=ttk.Scrollbar(box,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tree.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew')
        box.rowconfigure(0,weight=1);box.columnconfigure(0,weight=1)
        for key,title,width in zip(columns,labels,widths):tree.heading(key,text=title);tree.column(key,width=width,minwidth=70)
        return tree

    def config(self):
        scroll=float(self.scroll.get());refresh=int(self.refresh.get())
        if not 0.5<=scroll<=30 or not 10<=refresh<=3600:raise ValueError('Jeda scroll 0,5–30 detik; cek ulang 10–3600 detik.')
        return dict(headless=self.headless.get(),block_media=self.block.get(),summary=self.summary.get(),scroll=scroll,refresh=refresh)

    def start(self):
        try:
            if self.bot.running:raise ValueError('Stop proses aktif terlebih dahulu.')
            config=self.config();sid=self.store.create(self.name.get().strip(),self.url.get())
            self.selected=sid;self.offset=0;self.bot.start(sid,config);self.load_history()
        except Exception as exc:messagebox.showerror('Tidak bisa mulai',str(exc))

    def resume(self):
        if not self.selected:return
        try:self.bot.start(self.selected,self.config());self.status.set('Melanjutkan dari pencarian awal; hasil lama dideduplikasi.')
        except Exception as exc:messagebox.showerror('Tidak bisa lanjut',str(exc))

    def stop(self):
        self.bot.stop();self.status.set('Menghentikan proses dan menutup Firefox…')

    def pick(self,event=None):
        selected=self.hist.selection()
        if selected:
            self.selected=selected[0];self.offset=0;self.update_count()
            self.rows.delete(*self.rows.get_children())
            self.page_text.set('Klik Muat hasil. Ekspor selalu mengambil seluruh sesi.')

    def update_count(self):
        if self.selected:
            s=self.store.get(self.selected);self.count.set(f"{s['count']:,} pasangan · {s['name'][:35]}")

    def load_history(self):
        keep=self.selected;self.hist.delete(*self.hist.get_children())
        for s in self.store.history(self.history_offset):
            self.hist.insert('', 'end',iid=s['id'],values=(s['name'],s['count'],s['status'],s['created']))
        if keep and self.hist.exists(keep):self.hist.selection_set(keep)

    def history_page(self,delta):
        new=max(0,self.history_offset+delta)
        if new and not self.store.history(new):return
        self.history_offset=new;self.load_history()

    def load_rows(self):
        if not self.selected:return
        self.rows.delete(*self.rows.get_children());rows=self.store.rows(self.selected,self.offset)
        for r in rows:self.rows.insert('','end',values=(r['url'],'https://www.facebook.com/ads/library/?id='+r['ad_id']))
        self.page_text.set(f'{self.offset+1 if rows else 0}–{self.offset+len(rows)} · Ekspor mencakup seluruh sesi.')
        self.update_count()

    def page(self,delta):
        if not self.selected:return
        new=max(0,self.offset+delta)
        if new and not self.store.rows(self.selected,new):return
        self.offset=new;self.load_rows()

    def export(self):
        if not self.selected or (self.export_thread and self.export_thread.is_alive()):return
        sid=self.selected
        path=filedialog.asksaveasfilename(defaultextension='.csv',initialfile=f'adradar_{sid[:8]}.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        self.status.set('Mengekspor hasil…')
        def write():
            try:self.events.put(('export',sid,(self.store.export(sid,path),path)))
            except Exception as exc:self.events.put(('error',sid,str(exc)))
        self.export_thread=threading.Thread(target=write,daemon=True);self.export_thread.start()

    def delete(self):
        if not self.selected:return
        if self.bot.running and self.selected==self.bot.sid:
            messagebox.showinfo('Masih berjalan','Stop sesi ini sebelum dihapus.');return
        if self.export_thread and self.export_thread.is_alive():
            messagebox.showinfo('Ekspor berjalan','Tunggu ekspor selesai.');return
        if messagebox.askyesno('Hapus sesi','Hapus sesi terpilih dan semua hasilnya?'):
            self.store.delete(self.selected);self.selected=None;self.count.set('Pilih sesi.');self.rows.delete(*self.rows.get_children());self.load_history()

    def poll(self):
        try:
            for _ in range(100):
                kind,sid,value=self.events.get_nowait()
                if kind=='status':
                    self.status.set(value)
                    if self.hist.exists(sid):self.hist.set(sid,'status',self.store.get(sid)['status'])
                elif kind=='count':
                    if sid==self.selected:self.update_count()
                    if self.hist.exists(sid):self.hist.set(sid,'count',value)
                elif kind=='done':self.status.set(value);self.load_history()
                elif kind=='export':self.status.set(f'CSV tersimpan: {value[0]} baris · {value[1]}')
                elif kind=='error':messagebox.showerror('Gagal',value)
        except queue.Empty:pass
        active=self.bot.running;exporting=self.export_thread and self.export_thread.is_alive()
        self.start_btn.configure(state='disabled' if active or self.closing else 'normal')
        self.resume_btn.configure(state='disabled' if active or not self.selected or self.closing else 'normal')
        self.stop_btn.configure(state='normal' if active and not self.closing else 'disabled')
        self.export_btn.configure(state='disabled' if exporting or not self.selected or self.closing else 'normal')
        if self.closing and not active and not exporting:self.root.destroy();return
        self.root.after(300,self.poll)

    def close(self):
        self.closing=True;self.bot.stop();self.status.set('Menutup Firefox dan menyelesaikan penyimpanan…')
