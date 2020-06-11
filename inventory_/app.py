# imports - standard imports
import os
import json
from decimal import Decimal

# imports - third party imports
from flask import Flask, url_for, request, redirect
from flask import render_template as render
from flaskext.mysql import MySQL
 

# global constants



# setting up Flask instance
app = Flask(__name__)
mysql = MySQL()

app.config['TEMPLATES_AUTO_RELOAD'] = True
mysql = MySQL()
app = Flask(__name__)
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'password'
app.config['MYSQL_DATABASE_DB'] = 'db_name'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)
cnx = mysql.connect()
cursor = cnx.cursor()
# listing views
link = {x: x for x in ["summary","location", "product", "movement","customer"]}
link["login"] = '/'
app.secret_key = 'why would I tell you my secret key?'

@app.route('/')
def form():
    return render("login.html")

@app.route('/logins',methods=['POST'])
def login():
    # cursor.execute("SELECT * from login")
    cursor.execute("CALL getlogin()")
    data=cursor.fetchall()
    print(data[0][0])
    
    Name=request.form['name']
    Password=request.form['password']
    print(Name)
    print(Password)
    if (data[0][0]==Name) and (data[0][1]==Password): 
        return redirect(url_for('summary'))
    else:
        return print (f"Error in login")

@app.route('/summary')
def summary():
    
    msg = None
    q_data, warehouse, products = None, None, None
    
    try:
        # cursor.execute("SELECT * FROM location")  
        cursor.execute("CALL getlocation()")
        warehouse = cursor.fetchall()
        #cursor.execute("SELECT * FROM product")
        cursor.execute("CALL getproduct()")
        products = cursor.fetchall()
        cursor.execute("""
        SELECT prod_name, unallocated_quality, prod_quality FROM product
        """)
        q_data = cursor.fetchall()
    except mysql.Error as e:
        msg = f"An error occurred: {e.args[0]}"
    if msg:
        print(msg)

    return render('index.html', link=link, title="Summary", warehouses=warehouse, products=products, database=q_data)


@app.route('/product', methods=['POST', 'GET'])
def product():
    
    msg = None
    

    cursor.execute("SELECT * FROM product")
    products = cursor.fetchall()

    if request.method == 'POST':
        prod_name = request.form['prod_name']
        quantity = request.form['prod_quantity']

        transaction_allowed = False
        if prod_name not in ['', ' ', None]:
            if quantity not in ['', ' ', None]:
                transaction_allowed = True

        if transaction_allowed:
            try:
                cursor.execute("INSERT INTO product (prod_name, prod_quality) VALUES (%s, %s)", (prod_name, str(quantity)))
                cnx.commit()
                cursor.execute("UPDATE product set unallocated_quality= %s where prod_name=%s AND unallocated_quality IS NULL",(str(quantity),prod_name))
                cnx.commit()
            except mysql.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = f"{prod_name} added successfully"

            if msg:
                print(msg)

            return redirect(url_for('product'))

    return render('product.html',
                  link=link, products=products, transaction_message=msg,
                  title="Products Log")


@app.route('/location', methods=['POST', 'GET'])
def location():
    
    msg = None
    

    cursor.execute("SELECT * FROM location")
    warehouse_data = cursor.fetchall()

    if request.method == 'POST':
        warehouse_name = request.form['warehouse_name']

        transaction_allowed = False
        if warehouse_name not in ['', ' ', None]:
            transaction_allowed = True

        if transaction_allowed:
            try:
                cursor.execute("INSERT INTO location (loc_name) VALUES (%s)", (warehouse_name))
                cnx.commit()
            except mysql.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = f"{warehouse_name} added successfully"

            if msg:
                print(msg)

            return redirect(url_for('location'))

    return render('location.html',
                  link=link, warehouses=warehouse_data, transaction_message=msg,
                  title="Warehouse Locations")


@app.route('/movement', methods=['POST', 'GET'])
def movement():
    
    msg = None
    

    cursor.execute("SELECT * FROM logistics")
    logistics_data = cursor.fetchall()
    cursor.execute("SELECT prod_id, prod_name, unallocated_quality FROM product")
    products = cursor.fetchall()
    cursor.execute("SELECT * from summary")
    summary=cursor.fetchall()
    
    cursor.execute("SELECT loc_id, loc_name FROM location")
    locations = cursor.fetchall()

    log_summary = []
    for p_id in [x[0] for x in products]:
        cursor.execute("SELECT prod_name FROM product WHERE prod_id = %s", (p_id, ))
        temp_prod_name = cursor.fetchone()

        for l_id in [x[0] for x in locations]:
            cursor.execute("SELECT loc_name FROM location WHERE loc_id = %s", (l_id,))
            temp_loc_name = cursor.fetchone()

            cursor.execute("""
            SELECT SUM(log.prod_quality)
            FROM logistics log
            WHERE log.prod_id = %s AND log.to_loc_id = %s
            """, (p_id, l_id))
            sum_to_loc = cursor.fetchone()

            cursor.execute("""
            SELECT SUM(log.prod_quality)
            FROM logistics log
            WHERE log.prod_id = %s AND log.from_loc_id = %s
            """, (p_id, l_id))
            sum_from_loc = cursor.fetchone()

            if sum_from_loc[0] is None:
                sum_from_loc = (0,)
            if sum_to_loc[0] is None:
                sum_to_loc = (0,)
            cursor.execute("SELECT quantity from summary where prod_name=%s and loc_name=%s",(temp_prod_name,temp_loc_name))
            prodn=cursor.fetchone()
            cursor.execute("select SUM(quantity) from cus_sales where loc_name=%s",(temp_loc_name))
            place_sum=cursor.fetchone()
            if place_sum[0] is None:
                place_sum=(0,)

            if prodn:

                cursor.execute("UPDATE summary SET quantity=%s where prod_name=%s and loc_name=%s",(sum_to_loc[0] - sum_from_loc[0]-place_sum[0],temp_prod_name,temp_loc_name))
                cnx.commit()
            else:
                cursor.execute("INSERT INTO summary values(%s,%s,%s)",(temp_prod_name,temp_loc_name,sum_to_loc[0] - sum_from_loc[0]-place_sum[0]))
                cnx.commit()
            log_summary += [(temp_prod_name + temp_loc_name + (sum_to_loc[0] - sum_from_loc[0]-place_sum[0],))]
    
    
    alloc_json = {}
    for row in log_summary:
        try:
            if row[1] in alloc_json[row[0]].keys():
                alloc_json[row[0]][row[1]] += row[2]
               
            else:
                alloc_json[row[0]][row[1]] = row[2]
        except (KeyError, TypeError):
            alloc_json[row[0]] = {}
            alloc_json[row[0]][row[1]] = row[2]
    alloc_json = json.dumps(alloc_json,default=defaultencode)
    
    if request.method == 'POST':
        # transaction times are stored in UTC
        prod_name = request.form['prod_name']
        from_loc = request.form['from_loc']
        to_loc = request.form['to_loc']
        quantity = request.form['quantity']

        if from_loc in [None, '', ' ']:
            try:
                cursor.execute("""
                    INSERT INTO logistics (prod_id, to_loc_id, prod_quality) 
                    SELECT product.prod_id, location.loc_id, %s
                    FROM product, location 
                    WHERE product.prod_name = %s AND location.loc_name = %s
                """, (quantity, prod_name, to_loc))

                # Maintain consistency
                cursor.execute("""
                UPDATE product 
                SET unallocated_quality = unallocated_quality - %s
                WHERE prod_name = %s
                """, (quantity, prod_name))
                cnx.commit()

            except mysql.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"

        elif to_loc in [None, '', ' ']:
            print("To Location wasn't specified, will be unallocated")
            try:
                cursor.execute("""
                INSERT INTO logistics (prod_id, from_loc_id, prod_quality) 
                SELECT product.prod_id, location.loc_id, %s
                FROM product, location 
                WHERE product.prod_name = %s AND location.loc_name = %s
                """, (quantity, prod_name, from_loc))

                # IMPORTANT to maintain consistency
                cursor.execute("""
                UPDATE product
                SET unallocated_quality = unallocated_quality + %s
                WHERE prod_name = %s
                """, (quantity, prod_name))
                cnx.commit()

            except mysql.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"

        # if 'from loc' and 'to_loc' given the product is being shipped between warehouses
        else:
            try:
                cursor.execute("SELECT loc_id FROM location WHERE loc_name = %s", (from_loc,))
                from_loc = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("SELECT loc_id FROM location WHERE loc_name = %s", (to_loc,))
                to_loc = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("SELECT prod_id FROM product WHERE prod_name = %s", (prod_name,))
                prod_id = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("""
                INSERT INTO logistics (prod_id, from_loc_id, to_loc_id, prod_quality)
                VALUES (%s, %s, %s, %s)
                """, (prod_id, from_loc, to_loc, quantity))
                cnx.commit()

            except mysql.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"
            
        # print a transaction message if exists!
        if msg:
            print(msg)
            return redirect(url_for('movement'))
    #print(log_summary)
    return render('movement.html', title="ProductMovement",
                  link=link, trans_message=msg,
                  products=products, locations=locations, allocated=alloc_json,
                  logs=logistics_data, database=log_summary)

@app.route('/customer',methods=['POST', 'GET'])
def customer():
    msg=None
    cursor.execute("SELECT * from cus_sales")
    cus_data=cursor.fetchall()
    cursor.execute("SELECT * from summary")
    summary=cursor.fetchall()
    if request.method == 'POST':
        prod_name=request.form['prod_name']
        from_loc=request.form['from_loc']
        name=request.form['name']
        phone=request.form['phone']
        quantity=request.form['quantity']
        cursor.execute("SELECT quantity from summary where prod_name=%s and loc_name=%s",(prod_name,from_loc))
        quat=cursor.fetchone()
        cursor.execute("SELECT prod_quality from product where prod_name=%s ",(prod_name))
        pquat=cursor.fetchone()
        # print(quat)
        if int(quat[0])>=int(quantity):
            cursor.execute("SELECT loc_id from location where loc_name=%s",(from_loc))
            location=cursor.fetchone()
            cursor.execute("INSERT INTO costumer (prod_name,name,phone,loc_id,quantity) values (%s,%s,%s,%s,%s)",(prod_name,name,phone,location,quantity))
            
            cursor.execute("UPDATE product set prod_quality=%s where prod_name=%s",(int(pquat[0])-int(quantity),prod_name))
            
            cursor.execute("UPDATE summary set quantity=%s where prod_name=%s and loc_name=%s",(str(int(quat[0])-int(quantity)),prod_name,from_loc))
            cnx.commit()
    return render('customer.html',title='customer sales',link=link,database=summary,logs=cus_data)

@app.route('/delete')
def delete():
    type_ = request.args.get('type')
    

    if type_ == 'location':
        id_ = request.args.get('loc_id')

        cursor.execute("SELECT prod_id, SUM(prod_quality) FROM logistics WHERE to_loc_id = %s GROUP BY prod_id", (id_,))
        in_place = cursor.fetchall()

        cursor.execute("SELECT prod_id, SUM(prod_quality) FROM logistics WHERE from_loc_id = %s GROUP BY prod_id", (id_,))
        out_place = cursor.fetchall()

        # converting list of tuples to dict
        in_place = dict(in_place)
        out_place = dict(out_place)

        # print(in_place, out_place)
        all_place = {}
        for x in in_place.keys():
            if x in out_place.keys():
                all_place[x] = in_place[x] - out_place[x]
            else:
                all_place[x] = in_place[x]
        # print(all_place)

        for products_ in all_place.keys():
            cursor.execute("""
            UPDATE product SET unallocated_quality = unallocated_quality + %s WHERE prod_id = %s
            """, (all_place[products_], products_))
        cursor.execute("select loc_name from location where loc_id=%s",str(id_))
        loc_name=cursor.fetchone()
        cursor.execute("select prod_name from product where prod_id=%s",str(id_))
        prod_name=cursor.fetchone()
        cursor.execute("DELETE FROM location WHERE loc_id = %s", str(id_))
        cursor.execute("DELETE FROM summary where loc_name=%s ",(loc_name[0]))
        cursor.execute("UPDATE cus_sales set quantity=0 where loc_name=%s",(loc_name[0]))
        cnx.commit()

        return redirect(url_for('location'))

    elif type_ == 'product':
        id_ = request.args.get('prod_id')
        cursor.execute("select loc_name from location where loc_id=%s",str(id_))
        loc_name=cursor.fetchone()
        cursor.execute("select prod_name from product where prod_id=%s",str(id_))
        prod_name=cursor.fetchone()
        cursor.execute("DELETE FROM product WHERE prod_id = %s", str(id_))
        cursor.execute("DELETE FROM summary where  prod_name=%s",(prod_name[0]))
        cursor.execute("UPDATE cus_sales set quantity=0 where prod_name=%s",(prod_name[0]))

        cnx.commit()

        return redirect(url_for('product'))



@app.route('/edit', methods=['POST', 'GET'])
def edit():
    type_ = request.args.get('type')
    

    if type_ == 'location' and request.method == 'POST':
        loc_id = request.form['loc_id']
        loc_name = request.form['loc_name']

        if loc_name:
            cursor.execute("UPDATE location SET loc_name = %s WHERE loc_id = %s",( loc_name, str(loc_id)))
            cnx.commit()

        return redirect(url_for('location'))

    elif type_ == 'product' and request.method == 'POST':
        prod_id = request.form['prod_id']
        prod_name = request.form['prod_name']
        prod_quantity = request.form['prod_quantity']

        if prod_name:
            cursor.execute("UPDATE product SET prod_name = %s WHERE prod_id = %s", (prod_name, str(prod_id)))
        if prod_quantity:
            cursor.execute("SELECT prod_quality FROM product WHERE prod_id = %s", str(prod_id,))
            old_prod_quantity = cursor.fetchone()[0]
            cursor.execute("UPDATE product SET prod_quality = %s, unallocated_quality =  unallocated_quality + %s - %s"
                           "WHERE prod_id = %s", (str(prod_quantity),str(prod_quantity), str(old_prod_quantity), str(prod_id)))
        cnx.commit()

        return redirect(url_for('product'))

    return render(url_for(type_))
def defaultencode(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(repr(o))

if __name__=="__main__":
    app.run(debug=True)
#movement()